"""Request-scoped auditing. Never capture POST, query strings or personal field values.

Read events identify ORM records loaded while serving a request (a conservative
superset of displayed records). Raw SQL, values() and direct database access need
separate database auditing. Writes outside HTTP have no actor and remain visible.
"""
from contextvars import ContextVar
from uuid import uuid4
from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_init, pre_save, post_save, pre_delete, m2m_changed
from django.dispatch import receiver
from django.utils.cache import patch_cache_control

current = ContextVar('audit_request', default=None)
SENSITIVE = {'core.employeerecordcard', 'core.summarystatement', 'core.detailedstatement', 'core.accountingadjustment', 'auth.user', 'auth.group', 'core.employee', 'core.employeecategoryhistory',
    'core.travel', 'core.travelexpense', 'core.overnightstay', 'core.accommodationreceipt',
    'core.calculationsnapshot', 'core.settlementitem', 'core.travelattachment',
    'core.approvaldocument', 'core.useraccess', 'core.department', 'core.signatory',
    'core.applicationparameters'}

def emit(action, target_type='', target_id='', changed_fields=(), actor=None, status=None):
    from .models import AuditEvent
    state=current.get()
    if actor is None and state:
        actor=getattr(state['request'],'user',None)
    authenticated=actor is not None and actor.is_authenticated
    return AuditEvent.objects.create(
        actor_id=actor.pk if authenticated else None,
        actor_identifier=actor.get_username() if authenticated else '',
        request_id=state['id'] if state else None, action=action,
        target_type=target_type, target_id=str(target_id or ''),
        changed_fields=list(changed_fields), route=state.get('route','') if state else '',
        method=state['request'].method if state else '', status_code=status)

@receiver(post_init, dispatch_uid='audit_reads')
def loaded(sender, instance, **kwargs):
    state=current.get()
    if state and sender._meta.label_lower in SENSITIVE:
        pk=instance.__dict__.get(sender._meta.pk.attname)
        if pk is not None: state['reads'].add((sender._meta.label_lower,str(pk)))

@receiver(pre_save, dispatch_uid='audit_before_write')
def before_save(sender, instance, using, raw=False, update_fields=None, **kwargs):
    if raw or using!='default' or sender._meta.label_lower not in SENSITIVE: return
    names=[f.attname for f in sender._meta.concrete_fields if not f.primary_key and f.name not in {'last_login','updated_at'}]
    if update_fields is not None:
        names=[f.attname for f in sender._meta.concrete_fields if f.name in update_fields and f.attname in names]
    old=sender.objects.using(using).filter(pk=instance.pk).values(*names).first() if instance.pk else None
    instance._audit_changed=[name for name in names if old is None or old[name]!=getattr(instance,name)]

@receiver(post_save, dispatch_uid='audit_writes')
def saved(sender, instance, created, using, raw=False, **kwargs):
    if raw or using!='default' or sender._meta.label_lower not in SENSITIVE: return
    fields=getattr(instance,'_audit_changed',[])
    if created or fields:
        emit('create' if created else 'update',sender._meta.label_lower,instance.pk,fields)

@receiver(pre_delete, dispatch_uid='audit_deletes')
def deleted(sender, instance, using, **kwargs):
    if using=='default' and sender._meta.label_lower in SENSITIVE:
        emit('delete',sender._meta.label_lower,instance.pk)

@receiver(m2m_changed, dispatch_uid='audit_permissions')
def memberships(sender, instance, action, using, reverse, model, **kwargs):
    if using=='default' and action in {'post_add','post_remove','post_clear'} and instance._meta.label_lower in SENSITIVE:
        emit('permissions',instance._meta.label_lower,instance.pk,[sender._meta.model_name,action])

@receiver(user_logged_in, dispatch_uid='audit_login')
def login(sender, request, user, **kwargs): emit('login','auth.user',user.pk,actor=user)

@receiver(user_logged_out, dispatch_uid='audit_logout')
def logout(sender, request, user, **kwargs): emit('logout','auth.user',user.pk if user else '',actor=user)

@receiver(user_login_failed, dispatch_uid='audit_login_failure')
def failed(sender, credentials, request, **kwargs):
    # Submitted usernames and credentials deliberately excluded.
    emit('login_failed',status=401)

class AuditMiddleware:
    def __init__(self,get_response): self.get_response=get_response

    def process_view(self, request, view_func, view_args, view_kwargs):
        state=current.get()
        if state and request.resolver_match:
            state['route']=request.resolver_match.view_name

    def __call__(self,request):
        # SessionMiddleware has run; resolve the actor even on a CSRF rejection.
        from django.contrib.auth import get_user
        from django.utils.functional import SimpleLazyObject
        if not hasattr(request,'user'):
            request.user=SimpleLazyObject(lambda: get_user(request))
        state={'request':request,'id':uuid4(),'reads':set(),'route':''}
        token=current.set(state)
        try:
            response=self.get_response(request)
            match=request.resolver_match
            if match: state['route']=match.view_name
            relevant=bool(match and (match.app_name in {'core','admin'} or match.url_name in {
                'login','logout','password_change','password_change_done','password_reset_confirm'}))
            if relevant:
                route=match.view_name
                action='denied' if response.status_code in (401,403,404) else ('error' if response.status_code>=500 else 'access')
                if response.status_code==200 and ('download' in route or (route.endswith('other_documents') and request.method=='POST')):
                    action='download'
                emit(action,'endpoint',match.kwargs.get('pk',match.kwargs.get('object_id','')),status=response.status_code)
                # Track internal record reads also on denied/invalid requests; status prevents
                # confusing a denied lookup with a successful disclosure.
                for kind,pk in sorted(state['reads']): emit('view',kind,pk,status=response.status_code)
                patch_cache_control(response,private=True,no_store=True)
                response['X-Audit-Request-ID']=str(state['id'])
            return response
        finally:
            current.reset(token)

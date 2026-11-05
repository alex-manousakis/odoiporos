from django.db.models import Q
from .models import Employee, UserAccess


def policy(user):
    return UserAccess.objects.filter(user=user).first() if user.is_authenticated else None


def employee_scope(user):
    qs=Employee.objects.all()
    if not user.is_active:
        return qs.none()
    if user.is_superuser:
        return qs
    access=policy(user)
    if access:
        if access.scope=='all':
            return qs
        if access.scope=='department':
            return qs.filter(Q(user=user)|Q(department__in=access.departments.all()))
        return qs.filter(user=user)
    # Preserve existing accounts until explicitly configured in user management.
    if user.has_perm('core.view_travel') or user.has_perm('core.add_travel'):
        return qs
    return qs.filter(user=user)


def can_action(user,action):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if policy(user):
        return user.has_perm(f'core.{action}_travel')
    return user.has_perm(f'core.{action}_travel') or Employee.objects.filter(user=user,is_active=True).exists()


def navigation(request):
    from django.urls import reverse
    user=request.user
    create=can_action(user,'add')
    current=request.resolver_match.url_name if request.resolver_match else ''
    sections=[]

    def group(key,label,entries):
        items=[]
        for allowed,title,url_name,active_names in entries:
            if allowed:
                items.append({'label':title,'url':reverse(url_name if url_name=='password_change' else 'core:'+url_name),'active':current in active_names})
        if items:sections.append({'key':key,'label':label,'items':items,'active':any(i['active'] for i in items)})

    if user.is_authenticated:
        group('travel','Μετακινήσεις',[
            (can_action(user,'view'),'Πίνακας ελέγχου','dashboard',('dashboard',)),
            (can_action(user,'view'),'Μετακινήσεις','home',('home','travel_create','travel_detail','travel_edit','travel_costs','approval_create','approval_download','accounting_home','accounting_create','accounting_edit','accounting_adjustment')),
        ])
        group('routes','Διαδρομές',[
            (user.has_perm('core.view_route'),'Διαχείριση διαδρομών','routes',('routes','route_create','route_edit')),
            (user.has_perm('core.view_transportmode'),'Τρόποι μετακίνησης','transport_modes',('transport_modes','transport_mode_create','transport_mode_edit')),
            (user.has_perm('core.view_accommodationtype'),'Διαμονή σε','accommodation_types',('accommodation_types','accommodation_type_create','accommodation_type_edit')),
        ])
        group('employees','Εργαζόμενοι',[
            (user.has_perm('core.view_employee'),'Διαχείριση εργαζομένων','employees',('employees','employee_create','employee_edit')),
            (user.has_perm('core.view_position'),'Θέσεις','positions',('positions','positions_create','positions_edit')),
            (user.has_perm('core.view_employeecategory'),'Κατηγορίες','employee_categories',('employee_categories','employee_categories_create','employee_categories_edit')),
            (user.has_perm('core.view_speciality'),'Ειδικότητες','specialities',('specialities','specialities_create','specialities_edit')),
        ])
        group('reference','Βοηθητικά αρχεία',[
            (user.has_perm('core.view_department'),'Μονάδες','departments',('departments','departments_create','departments_edit')),
            (user.has_perm('core.view_signatory'),'Υπογραφές','signatories',('signatories','signatories_create','signatories_edit')),
            (user.has_perm('core.view_dailyallowancerate'),'Ημερήσια αποζημίωση','daily_allowances',('daily_allowances','daily_allowance_create','daily_allowance_edit')),
            (user.has_perm('core.view_accommodationrate'),'Έξοδα διανυκτέρευσης','accommodation_rates',('accommodation_rates','accommodation_rate_create','accommodation_rate_edit')),
            (user.has_perm('core.view_reporttext'),'Κείμενα εκτυπώσεων','report_texts',('report_texts',)),
            (user.has_perm('core.view_travelreason'),'Λόγοι μετακίνησης','travel_reasons',('travel_reasons','travel_reasons_create','travel_reasons_edit')),
            (user.has_perm('core.view_settlementperiod'),'Περίοδοι','periods',('periods','period_create','period_edit')),
        ])
        group('settings','Παράμετροι',[
            (user.has_perm('core.view_applicationparameters') or user.has_perm('core.change_applicationparameters'),'Παράμετροι εφαρμογής','parameters',('parameters',)),
            (user.is_superuser,'Χρήστες και δικαιώματα','users',('users','user_create','user_edit')),
            (user.is_superuser,'Δραστηριότητα','activity',('activity',)),
            (True,'Αλλαγή κωδικού πρόσβασης','password_change',('password_change','password_change_done')),
        ])
    return {'can_create_travel':create,'navigation_sections':sections}

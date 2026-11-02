# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Activity(models.Model):
    activity = models.AutoField(db_column='ACTIVITY', primary_key=True)  # Field name made lowercase.
    module = models.IntegerField(db_column='MODULE', blank=True, null=True)  # Field name made lowercase.
    recordid = models.IntegerField(db_column='RECORDID', blank=True, null=True)  # Field name made lowercase.
    tablename = models.CharField(db_column='TABLENAME', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    usr = models.IntegerField(db_column='USR', blank=True, null=True)  # Field name made lowercase.
    company = models.IntegerField(db_column='COMPANY', blank=True, null=True)  # Field name made lowercase.
    activitydate = models.DateTimeField(db_column='ACTIVITYDATE', blank=True, null=True)  # Field name made lowercase.
    action = models.IntegerField(db_column='ACTION', blank=True, null=True)  # Field name made lowercase.
    comments = models.CharField(db_column='COMMENTS', max_length=100, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'ACTIVITY'


class Branch(models.Model):
    branch = models.IntegerField(db_column='BRANCH', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=64, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    address = models.CharField(db_column='ADDRESS', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    district = models.CharField(db_column='DISTRICT', max_length=40, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    zip = models.CharField(db_column='ZIP', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    city = models.CharField(db_column='CITY', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    phone1 = models.CharField(db_column='PHONE1', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    phone2 = models.CharField(db_column='PHONE2', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    erpofferseries = models.IntegerField(db_column='ERPOFFERSERIES', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'BRANCH'


class Category(models.Model):
    category = models.IntegerField(db_column='CATEGORY', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS')  # Field name made lowercase.
    comments = models.CharField(db_column='COMMENTS', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'CATEGORY'


class Dailycompensation(models.Model):
    dailycompensation = models.AutoField(db_column='DAILYCOMPENSATION', primary_key=True)  # Field name made lowercase.
    abroad = models.SmallIntegerField(db_column='ABROAD', blank=True, null=True)  # Field name made lowercase.
    category = models.SmallIntegerField(db_column='CATEGORY', blank=True, null=True)  # Field name made lowercase.
    compwithoutovernight = models.FloatField(db_column='COMPWITHOUTOVERNIGHT', blank=True, null=True)  # Field name made lowercase.
    comp = models.FloatField(db_column='COMP', blank=True, null=True)  # Field name made lowercase.
    comp2 = models.FloatField(db_column='COMP2', blank=True, null=True)  # Field name made lowercase.
    comp3 = models.FloatField(db_column='COMP3', blank=True, null=True)  # Field name made lowercase.
    validfrom = models.DateField(db_column='VALIDFROM', blank=True, null=True)  # Field name made lowercase.
    validto = models.DateField(db_column='VALIDTO', blank=True, null=True)  # Field name made lowercase.
    comments = models.CharField(db_column='COMMENTS', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'DAILYCOMPENSATION'


class Department(models.Model):
    department = models.AutoField(db_column='DEPARTMENT', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS')  # Field name made lowercase.
    namegeniki = models.CharField(db_column='NAMEGENIKI', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    responsible = models.CharField(db_column='RESPONSIBLE', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    sortorder = models.IntegerField(db_column='SORTORDER', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'DEPARTMENT'


class Gender(models.Model):
    gender = models.AutoField(db_column='GENDER', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    text1 = models.CharField(db_column='TEXT1', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    text2 = models.CharField(db_column='TEXT2', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    text3 = models.CharField(db_column='TEXT3', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'GENDER'


class Hotelcost(models.Model):
    hotelcost = models.AutoField(db_column='HOTELCOST', primary_key=True)  # Field name made lowercase.
    abroad = models.SmallIntegerField(db_column='ABROAD', blank=True, null=True)  # Field name made lowercase.
    category = models.SmallIntegerField(db_column='CATEGORY', blank=True, null=True)  # Field name made lowercase.
    overnightdistancelimit = models.FloatField(db_column='OVERNIGHTDISTANCELIMIT', blank=True, null=True)  # Field name made lowercase.
    hotelcostlimit = models.FloatField(db_column='HOTELCOSTLIMIT', blank=True, null=True)  # Field name made lowercase.
    hotelcostexpcitylimit = models.FloatField(db_column='HOTELCOSTEXPCITYLIMIT', blank=True, null=True)  # Field name made lowercase.
    hotelcostisland = models.FloatField(db_column='HOTELCOSTISLAND', blank=True, null=True)  # Field name made lowercase.
    validfrom = models.DateField(db_column='VALIDFROM', blank=True, null=True)  # Field name made lowercase.
    validto = models.DateField(db_column='VALIDTO', blank=True, null=True)  # Field name made lowercase.
    comments = models.CharField(db_column='COMMENTS', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'HOTELCOST'


class Kmallowance(models.Model):
    kmallowance = models.AutoField(db_column='KMALLOWANCE', primary_key=True)  # Field name made lowercase.
    fromdate = models.DateField(db_column='FROMDATE', blank=True, null=True)  # Field name made lowercase.
    todate = models.DateField(db_column='TODATE', blank=True, null=True)  # Field name made lowercase.
    amount = models.FloatField(db_column='AMOUNT', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'KMALLOWANCE'


class Module(models.Model):
    module = models.IntegerField(db_column='MODULE', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS')  # Field name made lowercase.
    menu = models.SmallIntegerField(db_column='MENU', blank=True, null=True)  # Field name made lowercase.
    submenu = models.SmallIntegerField(db_column='SUBMENU', blank=True, null=True)  # Field name made lowercase.
    verticalmenu = models.CharField(db_column='VERTICALMENU', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    sortorder = models.SmallIntegerField(db_column='SORTORDER', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'MODULE'


class Overnightlines(models.Model):
    overnightlines = models.AutoField(db_column='OVERNIGHTLINES', primary_key=True)  # Field name made lowercase.
    travel = models.ForeignKey('Travel', models.DO_NOTHING, db_column='TRAVEL', blank=True, null=True)  # Field name made lowercase.
    overnightdate = models.DateField(db_column='OVERNIGHTDATE', blank=True, null=True)  # Field name made lowercase.
    overnightplace = models.IntegerField(db_column='OVERNIGHTPLACE', blank=True, null=True)  # Field name made lowercase.
    route = models.IntegerField(db_column='ROUTE', blank=True, null=True)  # Field name made lowercase.
    customovernightcity_nouse = models.CharField(db_column='CUSTOMOVERNIGHTCITY_NoUse', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    overnightcity = models.CharField(db_column='OVERNIGHTCITY', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    expensive = models.SmallIntegerField(db_column='EXPENSIVE', blank=True, null=True)  # Field name made lowercase.
    abroad = models.SmallIntegerField(db_column='ABROAD', blank=True, null=True)  # Field name made lowercase.
    compcategory = models.SmallIntegerField(db_column='COMPCATEGORY', blank=True, null=True)  # Field name made lowercase.
    cost = models.FloatField(db_column='COST', blank=True, null=True)  # Field name made lowercase.
    budget = models.FloatField(db_column='BUDGET', blank=True, null=True)  # Field name made lowercase.
    island = models.SmallIntegerField(db_column='ISLAND', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'OVERNIGHTLINES'


class Overnightplace(models.Model):
    overnightplace = models.AutoField(db_column='OVERNIGHTPLACE', primary_key=True)  # Field name made lowercase.
    code = models.CharField(db_column='CODE', max_length=10, db_collation='Greek_CI_AS')  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS')  # Field name made lowercase.
    hascost = models.SmallIntegerField(db_column='HASCOST', blank=True, null=True)  # Field name made lowercase.
    needrespstatement = models.SmallIntegerField(db_column='NEEDRESPSTATEMENT', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'OVERNIGHTPLACE'


class Params(models.Model):
    id = models.SmallIntegerField(db_column='ID', primary_key=True)  # Field name made lowercase.
    lasttravelnum = models.IntegerField(db_column='LASTTRAVELNUM', blank=True, null=True)  # Field name made lowercase.
    travelnumdigits = models.IntegerField(db_column='TRAVELNUMDIGITS', blank=True, null=True)  # Field name made lowercase.
    homedistancelimit = models.FloatField(db_column='HOMEDISTANCELIMIT', blank=True, null=True)  # Field name made lowercase.
    overnightdistancelimit = models.FloatField(db_column='OVERNIGHTDISTANCELIMIT', blank=True, null=True)  # Field name made lowercase.
    kmcost = models.FloatField(db_column='KMCOST', blank=True, null=True)  # Field name made lowercase.
    countriescomp2 = models.CharField(db_column='COUNTRIESCOMP2', max_length=70, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    countriescomp3 = models.CharField(db_column='COUNTRIESCOMP3', max_length=70, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    expensivecitiesingreece = models.CharField(db_column='EXPENSIVECITIESINGREECE', max_length=70, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    expensivecitiesabroad = models.CharField(db_column='EXPENSIVECITIESABROAD', max_length=70, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    allowedtravelsperyear = models.IntegerField(db_column='ALLOWEDTRAVELSPERYEAR', blank=True, null=True)  # Field name made lowercase.
    attachmentsfolder = models.CharField(db_column='ATTACHMENTSFOLDER', max_length=100, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    mtpy = models.FloatField(db_column='MTPY', blank=True, null=True)  # Field name made lowercase.
    geotee = models.FloatField(db_column='GEOTEE', blank=True, null=True)  # Field name made lowercase.
    ekkatharistis = models.CharField(db_column='EKKATHARISTIS', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    perifereiarxis = models.CharField(db_column='PERIFEREIARXIS', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    prosfonisiypografis = models.CharField(db_column='PROSFONISIYPOGRAFIS', max_length=80, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    prosfonisiproistamenou = models.CharField(db_column='PROSFONISIPROISTAMENOU', max_length=100, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    usernameproistamenou = models.CharField(db_column='USERNAMEPROISTAMENOU', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    countdistanceurl = models.TextField(db_column='COUNTDISTANCEURL', db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    defaultovernightplace = models.IntegerField(db_column='DEFAULTOVERNIGHTPLACE', blank=True, null=True)  # Field name made lowercase.
    defaulttransport = models.IntegerField(db_column='DEFAULTTRANSPORT', blank=True, null=True)  # Field name made lowercase.
    percentageofbudgetinc = models.FloatField(db_column='PERCENTAGEOFBUDGETINC', blank=True, null=True)  # Field name made lowercase.
    budgetdownlimit = models.FloatField(db_column='BUDGETDOWNLIMIT', blank=True, null=True)  # Field name made lowercase.
    roundtotalbudget = models.SmallIntegerField(db_column='ROUNDTOTALBUDGET', blank=True, null=True)  # Field name made lowercase.
    username_anapl_proistamenou = models.CharField(db_column='USERNAME_ANAPL_PROISTAMENOU', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'PARAMS'


class Period(models.Model):
    period = models.AutoField(db_column='PERIOD', primary_key=True)  # Field name made lowercase.
    year = models.CharField(db_column='YEAR', max_length=4, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    code = models.CharField(db_column='CODE', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    fromdate = models.DateField(db_column='FROMDATE', blank=True, null=True)  # Field name made lowercase.
    todate = models.DateField(db_column='TODATE', blank=True, null=True)  # Field name made lowercase.
    aa = models.CharField(db_column='AA', max_length=5, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    hasmtpy = models.SmallIntegerField(db_column='HASMTPY', blank=True, null=True)  # Field name made lowercase.
    hasgeotee = models.SmallIntegerField(db_column='HASGEOTEE', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'PERIOD'


class Position(models.Model):
    position = models.AutoField(db_column='POSITION', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    namegeniki = models.CharField(db_column='NAMEGENIKI', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'POSITION'


class Reason(models.Model):
    reason = models.AutoField(db_column='REASON', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'REASON'


class Reportname(models.Model):
    reportname = models.IntegerField(db_column='REPORTNAME', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=100, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'REPORTNAME'


class Reportscript(models.Model):
    script = models.AutoField(db_column='SCRIPT', primary_key=True)  # Field name made lowercase.
    reportname = models.IntegerField(db_column='REPORTNAME', blank=True, null=True)  # Field name made lowercase.
    sortorder = models.IntegerField(db_column='SORTORDER', blank=True, null=True)  # Field name made lowercase.
    text = models.TextField(db_column='TEXT', db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'REPORTSCRIPT'


class Route(models.Model):
    route = models.AutoField(db_column='ROUTE', primary_key=True)  # Field name made lowercase.
    code_nouse = models.CharField(db_column='CODE_NoUse', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    fromcity = models.CharField(db_column='FROMCITY', max_length=30, db_collation='Greek_CI_AS')  # Field name made lowercase.
    tocity = models.CharField(db_column='TOCITY', max_length=80, db_collation='Greek_CI_AS')  # Field name made lowercase.
    name_nouse = models.CharField(db_column='NAME_NoUse', max_length=60, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    shortname = models.CharField(db_column='SHORTNAME', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    distance = models.FloatField(db_column='DISTANCE', blank=True, null=True)  # Field name made lowercase.
    abroad = models.SmallIntegerField(db_column='ABROAD', blank=True, null=True)  # Field name made lowercase.
    expensive = models.CharField(db_column='EXPENSIVE', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    compcategory = models.CharField(db_column='COMPCATEGORY', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    expensive_nouse = models.SmallIntegerField(db_column='EXPENSIVE_NoUse', blank=True, null=True)  # Field name made lowercase.
    hasdailycompensation = models.SmallIntegerField(db_column='HASDAILYCOMPENSATION', blank=True, null=True)  # Field name made lowercase.
    comments = models.CharField(db_column='COMMENTS', max_length=100, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    forcheck = models.SmallIntegerField(db_column='FORCHECK', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE')  # Field name made lowercase.
    insuser = models.CharField(db_column='INSUSER', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    is_in_island = models.CharField(db_column='IS_IN_ISLAND', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'ROUTE'


class Signature(models.Model):
    signature = models.AutoField(db_column='SIGNATURE', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    speciality = models.CharField(db_column='SPECIALITY', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'SIGNATURE'


class Speciality(models.Model):
    speciality = models.AutoField(db_column='SPECIALITY', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'SPECIALITY'


class Status(models.Model):
    status = models.SmallIntegerField(db_column='STATUS', primary_key=True)  # Field name made lowercase.
    statusname = models.CharField(db_column='STATUSNAME', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'STATUS'


class Transport(models.Model):
    transport = models.AutoField(db_column='TRANSPORT', primary_key=True)  # Field name made lowercase.
    code = models.CharField(db_column='CODE', max_length=10, db_collation='Greek_CI_AS')  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS')  # Field name made lowercase.
    hasprivatecost = models.SmallIntegerField(db_column='HASPRIVATECOST', blank=True, null=True)  # Field name made lowercase.
    haspubliccost = models.SmallIntegerField(db_column='HASPUBLICCOST', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'TRANSPORT'


class Travel(models.Model):
    travel = models.AutoField(db_column='TRAVEL', primary_key=True)  # Field name made lowercase.
    travelnum = models.CharField(db_column='TRAVELNUM', max_length=15, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    employee = models.IntegerField(db_column='EMPLOYEE', blank=True, null=True)  # Field name made lowercase.
    protocolnumber = models.CharField(db_column='PROTOCOLNUMBER', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    protocoldate = models.DateTimeField(db_column='PROTOCOLDATE', blank=True, null=True)  # Field name made lowercase.
    creationdate = models.DateTimeField(db_column='CREATIONDATE')  # Field name made lowercase.
    fromtraveldate = models.DateTimeField(db_column='FROMTRAVELDATE')  # Field name made lowercase.
    totraveldate = models.DateTimeField(db_column='TOTRAVELDATE', blank=True, null=True)  # Field name made lowercase.
    fromworkdate = models.DateTimeField(db_column='FROMWORKDATE', blank=True, null=True)  # Field name made lowercase.
    toworkdate = models.DateTimeField(db_column='TOWORKDATE', blank=True, null=True)  # Field name made lowercase.
    approveddate = models.DateTimeField(db_column='APPROVEDDATE', blank=True, null=True)  # Field name made lowercase.
    daysnearhome = models.FloatField(db_column='DAYSNEARHOME', blank=True, null=True)  # Field name made lowercase.
    daysawayhome = models.FloatField(db_column='DAYSAWAYHOME', blank=True, null=True)  # Field name made lowercase.
    daysabroad = models.FloatField(db_column='DAYSABROAD', blank=True, null=True)  # Field name made lowercase.
    compensationfactor = models.FloatField(db_column='COMPENSATIONFACTOR', blank=True, null=True)  # Field name made lowercase.
    compensationfactorabroad = models.FloatField(db_column='COMPENSATIONFACTORABROAD', blank=True, null=True)  # Field name made lowercase.
    totaldailycompensation = models.FloatField(db_column='TOTALDAILYCOMPENSATION', blank=True, null=True)  # Field name made lowercase.
    totaldailycompensationabroad = models.FloatField(db_column='TOTALDAILYCOMPENSATIONABROAD', blank=True, null=True)  # Field name made lowercase.
    overnights = models.FloatField(db_column='OVERNIGHTS', blank=True, null=True)  # Field name made lowercase.
    overnightbudget = models.FloatField(db_column='OVERNIGHTBUDGET', blank=True, null=True)  # Field name made lowercase.
    overnightcost = models.FloatField(db_column='OVERNIGHTCOST', blank=True, null=True)  # Field name made lowercase.
    travelcostpublic = models.FloatField(db_column='TRAVELCOSTPUBLIC', blank=True, null=True)  # Field name made lowercase.
    travelcostprivate = models.FloatField(db_column='TRAVELCOSTPRIVATE', blank=True, null=True)  # Field name made lowercase.
    travelcostrest = models.FloatField(db_column='TRAVELCOSTREST', blank=True, null=True)  # Field name made lowercase.
    totaldistance = models.FloatField(db_column='TOTALDISTANCE', blank=True, null=True)  # Field name made lowercase.
    traveldistanceprivate = models.FloatField(db_column='TRAVELDISTANCEPRIVATE', blank=True, null=True)  # Field name made lowercase.
    totalbudget = models.FloatField(db_column='TOTALBUDGET', blank=True, null=True)  # Field name made lowercase.
    prognosis = models.FloatField(db_column='PROGNOSIS', blank=True, null=True)  # Field name made lowercase.
    status = models.IntegerField(db_column='STATUS')  # Field name made lowercase.
    reason = models.IntegerField(db_column='REASON', blank=True, null=True)  # Field name made lowercase.
    purpose = models.CharField(db_column='PURPOSE', max_length=300, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    actionsdescription = models.TextField(db_column='ACTIONSDESCRIPTION', db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    overnightplace_todel = models.CharField(db_column='OVERNIGHTPLACE_todel', max_length=200, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    fromcity = models.CharField(db_column='FROMCITY', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    destinations = models.CharField(db_column='DESTINATIONS', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    attachment = models.CharField(db_column='ATTACHMENT', max_length=200, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    comments = models.CharField(db_column='COMMENTS', max_length=200, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    audit = models.CharField(db_column='AUDIT', max_length=300, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    forcheck = models.SmallIntegerField(db_column='FORCHECK', blank=True, null=True)  # Field name made lowercase.
    user_kmcost = models.FloatField(db_column='USER_KMCOST', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'TRAVEL'


class Travellines(models.Model):
    travellines = models.AutoField(db_column='TRAVELLINES', primary_key=True)  # Field name made lowercase.
    travel = models.ForeignKey(Travel, models.DO_NOTHING, db_column='TRAVEL')  # Field name made lowercase.
    route = models.ForeignKey(Route, models.DO_NOTHING, db_column='ROUTE', blank=True, null=True)  # Field name made lowercase.
    customroute = models.CharField(db_column='CUSTOMROUTE', max_length=70, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    distance = models.FloatField(db_column='DISTANCE', blank=True, null=True)  # Field name made lowercase.
    transport = models.ForeignKey(Transport, models.DO_NOTHING, db_column='TRANSPORT', blank=True, null=True)  # Field name made lowercase.
    overnightplace = models.IntegerField(db_column='OVERNIGHTPLACE', blank=True, null=True)  # Field name made lowercase.
    cost = models.FloatField(db_column='COST', blank=True, null=True)  # Field name made lowercase.
    restcost = models.FloatField(db_column='RESTCOST', blank=True, null=True)  # Field name made lowercase.
    attachment = models.CharField(db_column='ATTACHMENT', max_length=70, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    comments = models.CharField(db_column='COMMENTS', max_length=100, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    iscanceled = models.SmallIntegerField(db_column='ISCANCELED', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'TRAVELLINES'


class Userright(models.Model):
    userright = models.AutoField(db_column='USERRIGHT', primary_key=True)  # Field name made lowercase.
    usr = models.ForeignKey('Usr', models.DO_NOTHING, db_column='USR')  # Field name made lowercase.
    perm_view = models.SmallIntegerField(db_column='PERM_VIEW')  # Field name made lowercase.
    perm_create = models.SmallIntegerField(db_column='PERM_CREATE')  # Field name made lowercase.
    perm_update = models.SmallIntegerField(db_column='PERM_UPDATE')  # Field name made lowercase.
    perm_delete = models.SmallIntegerField(db_column='PERM_DELETE')  # Field name made lowercase.
    perm_print = models.SmallIntegerField(db_column='PERM_PRINT')  # Field name made lowercase.
    module = models.ForeignKey(Module, models.DO_NOTHING, db_column='MODULE')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'USERRIGHT'


class Usr(models.Model):
    usr = models.AutoField(db_column='USR', primary_key=True)  # Field name made lowercase.
    code = models.CharField(db_column='CODE', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    username = models.CharField(db_column='USERNAME', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    firstname = models.CharField(db_column='FIRSTNAME', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    lastname = models.CharField(db_column='LASTNAME', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    name = models.CharField(db_column='NAME', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    namegeniki = models.CharField(db_column='NAMEGENIKI', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    gender = models.ForeignKey(Gender, models.DO_NOTHING, db_column='GENDER', blank=True, null=True)  # Field name made lowercase.
    password = models.CharField(db_column='PASSWORD', max_length=25, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    idno = models.CharField(db_column='IDNO', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    vatno = models.CharField(db_column='VATNO', max_length=15, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    fathername = models.CharField(db_column='FATHERNAME', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    mothername = models.CharField(db_column='MOTHERNAME', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    placeofbirth = models.CharField(db_column='PLACEOFBIRTH', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    dateofbirth = models.DateField(db_column='DATEOFBIRTH', blank=True, null=True)  # Field name made lowercase.
    phone = models.CharField(db_column='PHONE', max_length=22, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    city = models.CharField(db_column='CITY', max_length=30, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    address = models.CharField(db_column='ADDRESS', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    addressnum = models.CharField(db_column='ADDRESSNUM', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    zip = models.CharField(db_column='ZIP', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    fax = models.CharField(db_column='FAX', max_length=15, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    email = models.CharField(db_column='EMAIL', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    drivinglicense = models.CharField(db_column='DRIVINGLICENSE', max_length=20, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    carplate = models.CharField(db_column='CARPLATE', max_length=10, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    carbrand = models.CharField(db_column='CARBRAND', max_length=15, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    iban = models.CharField(db_column='IBAN', max_length=50, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    department = models.ForeignKey(Department, models.DO_NOTHING, db_column='DEPARTMENT', blank=True, null=True)  # Field name made lowercase.
    category = models.ForeignKey(Category, models.DO_NOTHING, db_column='CATEGORY', blank=True, null=True)  # Field name made lowercase.
    speciality = models.ForeignKey(Speciality, models.DO_NOTHING, db_column='SPECIALITY', blank=True, null=True)  # Field name made lowercase.
    position = models.ForeignKey(Position, models.DO_NOTHING, db_column='POSITION', blank=True, null=True)  # Field name made lowercase.
    hasmtpy = models.IntegerField(db_column='HASMTPY', blank=True, null=True)  # Field name made lowercase.
    hasgeotee = models.IntegerField(db_column='HASGEOTEE', blank=True, null=True)  # Field name made lowercase.
    travelstillstart = models.IntegerField(db_column='TRAVELSTILLSTART', blank=True, null=True)  # Field name made lowercase.
    allusersaccess = models.SmallIntegerField(db_column='ALLUSERSACCESS', blank=True, null=True)  # Field name made lowercase.
    commentsemployee = models.CharField(db_column='COMMENTSEMPLOYEE', max_length=100, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    commentsuser = models.CharField(db_column='COMMENTSUSER', max_length=100, db_collation='Greek_CI_AS', blank=True, null=True)  # Field name made lowercase.
    isactive = models.SmallIntegerField(db_column='ISACTIVE', blank=True, null=True)  # Field name made lowercase.
    isemployee = models.SmallIntegerField(db_column='ISEMPLOYEE', blank=True, null=True)  # Field name made lowercase.
    can_add_route = models.SmallIntegerField(db_column='CAN_ADD_ROUTE', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'USR'


class Sysdiagrams(models.Model):
    name = models.CharField(max_length=128, db_collation='Greek_CI_AS')
    principal_id = models.IntegerField()
    diagram_id = models.AutoField(primary_key=True)
    version = models.IntegerField(blank=True, null=True)
    definition = models.BinaryField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sysdiagrams'
        unique_together = (('principal_id', 'name'),)

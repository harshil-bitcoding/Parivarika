def is_demo_login(request):
    # 1. Check Header (Primary for most APIs)
    mobile = request.headers.get("X-Mobile-Number")
    
    # 2. Check Body (Specifically for the Login API)
    if not mobile and hasattr(request, 'data'):
        mobile = request.data.get("mobile_number")
        
    return mobile == "1111111111"

def get_person_queryset(request):
    from .models import Person
    is_demo = is_demo_login(request)
    return Person.objects.filter(is_demo=is_demo, is_deleted=False)

def get_relation_queryset(request):
    from .models import ParentChildRelation
    is_demo = is_demo_login(request)
    return ParentChildRelation.objects.filter(is_demo=is_demo, is_deleted=False)

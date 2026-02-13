from .models import Company

def selected_company(request):
    company_id = request.session.get('selected_company_id')
    company = Company.objects.filter(id=company_id).first() if company_id else None
    return {
        'selected_company': company,
        'companies': Company.objects.all()
    }


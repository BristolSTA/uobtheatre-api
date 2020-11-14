from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView

from .models import Document


class DocumentCreateView(CreateView):
    model = Document
    fields = [
        "upload",
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        documents = Document.objects.all()
        context["documents"] = documents
        return context

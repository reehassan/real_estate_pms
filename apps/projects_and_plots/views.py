from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Project, Plot


# ─────────────────────────────
# PROJECT VIEWS
# ─────────────────────────────

class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects_and_plots/project_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.filter(is_deleted=False)


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "projects_and_plots/project_detail.html"
    context_object_name = "project"


# ─────────────────────────────
# PLOT VIEWS
# ─────────────────────────────

class PlotListView(LoginRequiredMixin, ListView):
    model = Plot
    template_name = "projects_and_plots/plot_list.html"
    context_object_name = "plots"

    def get_queryset(self):
        return Plot.objects.filter(is_deleted=False).select_related("project")


class PlotDetailView(LoginRequiredMixin, DetailView):
    model = Plot
    template_name = "projects_and_plots/plot_detail.html"
    context_object_name = "plot"
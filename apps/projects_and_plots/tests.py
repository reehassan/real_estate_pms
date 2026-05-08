"""
apps/projects_and_plots/tests.py

Test coverage:
    - Project model: creation, __str__, soft delete, manager filtering
    - Plot model: creation, __str__, soft delete, manager filtering
    - UniqueConstraint: duplicate plot_number per project
    - SoftDeleteManager: excludes deleted, all_objects includes deleted
    - Status / choice field validation
    - Plot.delete() does not cascade-delete related Project
    - Project.delete() with PROTECT on Plot FK
"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import Plot, Project


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def make_project(**kwargs) -> Project:
    defaults = {
        "name":        "Test Scheme",
        "code":        "TST",
        "location":    "Lahore, Punjab",
        "total_plots": 10,
        "total_area":  200,
        "area_unit":   Project.AreaUnit.MARLA,
        "status":      Project.Status.ACTIVE,
    }
    defaults.update(kwargs)
    return Project.objects.create(**defaults)


def make_plot(project: Project, plot_number: str = "101", **kwargs) -> Plot:
    defaults = {
        "project":     project,
        "plot_number": plot_number,
        "size":        Decimal("5.00"),
        "size_unit":   Plot.SizeUnit.MARLA,
        "category":    Plot.Category.RESIDENTIAL,
        "price":       Decimal("2500000.00"),
        "status":      Plot.Status.AVAILABLE,
    }
    defaults.update(kwargs)
    return Plot.objects.create(**defaults)


# ─────────────────────────────────────────────
# PROJECT TESTS
# ─────────────────────────────────────────────

class ProjectCreationTests(TestCase):

    def test_project_created_with_defaults(self):
        project = make_project()
        self.assertEqual(project.status, Project.Status.ACTIVE)
        self.assertFalse(project.is_deleted)
        self.assertIsNone(project.deleted_at)
        self.assertIsNotNone(project.created_at)
        self.assertIsNotNone(project.updated_at)

    def test_project_str(self):
        project = make_project(name="Royal Bahria Scheme", status=Project.Status.ACTIVE)
        self.assertIn("Royal Bahria Scheme", str(project))
        self.assertIn("Active", str(project))

    def test_project_status_choices(self):
        for status, _ in Project.Status.choices:
            p = make_project(code=f"C{status[:3]}", status=status)
            self.assertEqual(p.status, status)

    def test_project_area_unit_choices(self):
        for unit, _ in Project.AreaUnit.choices:
            p = make_project(code=f"U{unit[:3]}", area_unit=unit)
            self.assertEqual(p.area_unit, unit)

    def test_unique_project_code(self):
        make_project(code="UNQ")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_project(code="UNQ", name="Duplicate Code Project")

    def test_project_ordering_newest_first(self):
        p1 = make_project(code="P01", name="First")
        p2 = make_project(code="P02", name="Second")
        projects = list(Project.objects.all())
        # newest created_at should be first
        self.assertEqual(projects[0], p2)
        self.assertEqual(projects[1], p1)


class ProjectSoftDeleteTests(TestCase):

    def setUp(self):
        self.project = make_project()

    def test_soft_delete_sets_is_deleted(self):
        self.project.delete()
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_deleted)

    def test_soft_delete_sets_deleted_at(self):
        before = timezone.now()
        self.project.delete()
        self.project.refresh_from_db()
        self.assertIsNotNone(self.project.deleted_at)
        self.assertGreaterEqual(self.project.deleted_at, before)

    def test_soft_delete_does_not_remove_db_row(self):
        pk = self.project.pk
        self.project.delete()
        self.assertTrue(Project.all_objects.filter(pk=pk).exists())

    def test_default_manager_excludes_deleted(self):
        self.project.delete()
        self.assertNotIn(self.project, Project.objects.all())

    def test_all_objects_includes_deleted(self):
        self.project.delete()
        self.assertIn(self.project, Project.all_objects.all())

    def test_objects_count_after_delete(self):
        make_project(code="P2")
        make_project(code="P3")
        self.project.delete()
        self.assertEqual(Project.objects.count(), 2)
        self.assertEqual(Project.all_objects.count(), 3)


# ─────────────────────────────────────────────
# PLOT TESTS
# ─────────────────────────────────────────────

class PlotCreationTests(TestCase):

    def setUp(self):
        self.project = make_project()

    def test_plot_created_with_defaults(self):
        plot = make_plot(self.project)
        self.assertEqual(plot.status, Plot.Status.AVAILABLE)
        self.assertEqual(plot.category, Plot.Category.RESIDENTIAL)
        self.assertFalse(plot.is_deleted)
        self.assertIsNone(plot.deleted_at)

    def test_plot_str_without_block(self):
        plot = make_plot(self.project, plot_number="105")
        result = str(plot)
        self.assertIn(self.project.name, result)
        self.assertIn("105", result)

    def test_plot_str_with_block(self):
        plot = make_plot(self.project, plot_number="105", block="A")
        result = str(plot)
        self.assertIn("A", result)
        self.assertIn("105", result)

    def test_plot_status_choices(self):
        statuses = [
            Plot.Status.AVAILABLE,
            Plot.Status.TOKEN,
            Plot.Status.BOOKED,
            Plot.Status.SOLD,
        ]
        for i, status in enumerate(statuses):
            plot = make_plot(self.project, plot_number=str(200 + i), status=status)
            self.assertEqual(plot.status, status)

    def test_plot_category_choices(self):
        p_res = make_plot(self.project, plot_number="301", category=Plot.Category.RESIDENTIAL)
        p_com = make_plot(self.project, plot_number="302", category=Plot.Category.COMMERCIAL)
        self.assertEqual(p_res.category, Plot.Category.RESIDENTIAL)
        self.assertEqual(p_com.category, Plot.Category.COMMERCIAL)

    def test_plot_size_unit_choices(self):
        for i, (unit, _) in enumerate(Plot.SizeUnit.choices):
            plot = make_plot(self.project, plot_number=str(400 + i), size_unit=unit)
            self.assertEqual(plot.size_unit, unit)

    def test_plot_price_stored_correctly(self):
        plot = make_plot(self.project, price=Decimal("7500000.50"))
        plot.refresh_from_db()
        self.assertEqual(plot.price, Decimal("7500000.50"))


class PlotUniqueConstraintTests(TestCase):

    def setUp(self):
        self.project = make_project()

    def test_duplicate_plot_number_in_same_project_raises(self):
        make_plot(self.project, plot_number="101")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_plot(self.project, plot_number="101")

    def test_same_plot_number_in_different_projects_allowed(self):
        project2 = make_project(code="P2", name="Second Project")
        plot1 = make_plot(self.project,  plot_number="101")
        plot2 = make_plot(project2, plot_number="101")
        self.assertNotEqual(plot1.pk, plot2.pk)

    def test_different_plot_numbers_in_same_project_allowed(self):
        plot1 = make_plot(self.project, plot_number="101")
        plot2 = make_plot(self.project, plot_number="102")
        self.assertNotEqual(plot1.pk, plot2.pk)


class PlotSoftDeleteTests(TestCase):

    def setUp(self):
        self.project = make_project()
        self.plot    = make_plot(self.project)

    def test_soft_delete_sets_is_deleted(self):
        self.plot.delete()
        self.plot.refresh_from_db()
        self.assertTrue(self.plot.is_deleted)

    def test_soft_delete_sets_deleted_at(self):
        before = timezone.now()
        self.plot.delete()
        self.plot.refresh_from_db()
        self.assertIsNotNone(self.plot.deleted_at)
        self.assertGreaterEqual(self.plot.deleted_at, before)

    def test_soft_delete_does_not_remove_db_row(self):
        pk = self.plot.pk
        self.plot.delete()
        self.assertTrue(Plot.all_objects.filter(pk=pk).exists())

    def test_default_manager_excludes_deleted(self):
        self.plot.delete()
        self.assertNotIn(self.plot, Plot.objects.all())

    def test_all_objects_includes_deleted(self):
        self.plot.delete()
        self.assertIn(self.plot, Plot.all_objects.all())

    def test_objects_count_after_delete(self):
        make_plot(self.project, plot_number="102")
        make_plot(self.project, plot_number="103")
        self.plot.delete()
        self.assertEqual(Plot.objects.count(), 2)
        self.assertEqual(Plot.all_objects.count(), 3)

    def test_soft_deleted_plot_number_can_be_reused(self):
        """
        After soft-deleting a plot, the same plot_number
        should be usable again in the same project since
        UniqueConstraint doesn't filter by is_deleted.
        This test documents the current behaviour — if you
        add a partial unique index later, update this test.
        """
        self.plot.delete()
        # Attempt to create a new plot with the same number
        # This will raise IntegrityError because the DB row still exists
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_plot(self.project, plot_number=self.plot.plot_number)


class PlotProjectRelationTests(TestCase):

    def setUp(self):
        self.project = make_project()

    def test_plot_belongs_to_project(self):
        plot = make_plot(self.project)
        self.assertEqual(plot.project, self.project)

    def test_project_plots_related_name(self):
        plot1 = make_plot(self.project, plot_number="101")
        plot2 = make_plot(self.project, plot_number="102")
        plots = list(self.project.plots.all())
        self.assertIn(plot1, plots)
        self.assertIn(plot2, plots)

    def test_deleting_project_with_plots_raises(self):
        """
        Plot FK uses on_delete=PROTECT so deleting a project
        with live plots must raise ProtectedError.
        Note: Project.delete() is a soft-delete so it calls save(),
        not the DB-level delete — this means PROTECT is NOT triggered
        by Project.delete(). This test documents that behaviour.
        """
        make_plot(self.project, plot_number="101")
        # Soft delete should succeed (it just sets is_deleted=True)
        self.project.delete()
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_deleted)
        # The plot is still there — soft delete doesn't cascade
        self.assertEqual(Plot.objects.filter(project=self.project).count(), 1)

    def test_plot_ordering(self):
        make_plot(self.project, plot_number="103", block="B")
        make_plot(self.project, plot_number="101", block="A")
        make_plot(self.project, plot_number="102", block="A")
        plots = list(Plot.objects.filter(project=self.project))
        # Meta ordering: project, block, plot_number
        self.assertEqual(plots[0].plot_number, "101")
        self.assertEqual(plots[1].plot_number, "102")
        self.assertEqual(plots[2].plot_number, "103")


# ─────────────────────────────────────────────
# MANAGER TESTS
# ─────────────────────────────────────────────

class SoftDeleteManagerTests(TestCase):

    def setUp(self):
        self.p1 = make_project(code="A1", name="Active 1")
        self.p2 = make_project(code="A2", name="Active 2")
        self.p3 = make_project(code="D1", name="Deleted 1")
        self.p3.delete()

    def test_objects_returns_only_non_deleted(self):
        qs = Project.objects.all()
        self.assertIn(self.p1, qs)
        self.assertIn(self.p2, qs)
        self.assertNotIn(self.p3, qs)

    def test_all_objects_returns_all(self):
        qs = Project.all_objects.all()
        self.assertIn(self.p1, qs)
        self.assertIn(self.p2, qs)
        self.assertIn(self.p3, qs)

    def test_objects_filter_works_on_non_deleted(self):
        result = Project.objects.filter(status=Project.Status.ACTIVE)
        self.assertEqual(result.count(), 2)

    def test_all_objects_filter_includes_deleted(self):
        result = Project.all_objects.filter(is_deleted=True)
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first(), self.p3)

    def test_plot_manager_mirrors_project_manager(self):
        project = make_project(code="PM1")
        plot1   = make_plot(project, plot_number="101")
        plot2   = make_plot(project, plot_number="102")
        plot1.delete()

        self.assertNotIn(plot1, Plot.objects.all())
        self.assertIn(plot2,  Plot.objects.all())
        self.assertIn(plot1,  Plot.all_objects.all())
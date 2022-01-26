from admin_confirm.admin import AdminConfirmMixin
from admin_confirm.utils import snake_to_title_case
from django.contrib.admin import TabularInline, helpers
from django.contrib.admin.options import InlineModelAdmin
from django_celery_results.models import TaskResult


class ReadOnlyInlineMixin(InlineModelAdmin):
    """A mixin that provides a read only inline model admin class"""

    show_change_link = True

    def has_change_permission(self, _, __=None):
        return False

    def has_add_permission(self, _, __=None):
        return False

    def has_delete_permission(self, _, __=None):
        return False


def confirm_dangerous_action(func):
    """
    @confirm_dangerous_action function wrapper for Django ModelAdmin actions
    Will redirect to a confirmation page to ask for confirmation

    Next, it would call the action if confirmed. Otherwise, it would
    return to the changelist without performing action.
    """

    def func_wrapper(modeladmin, request, queryset):
        action_display_name = snake_to_title_case(func.__name__)

        # First called by `Go` which would not have confirm_action in params
        if (
            request.POST.get("_confirm_action")
            and request.POST.get("_confirm_action_confirmation")
            == "I want to %s" % action_display_name
        ):
            return func(modeladmin, request, queryset)

        # get_actions will only return the actions that are allowed
        has_perm = modeladmin.get_actions(request).get(func.__name__) is not None
        title = f"Confirm Action: {action_display_name}"

        context = {
            **modeladmin.admin_site.each_context(request),
            "title": title,
            "queryset": queryset,
            "has_perm": has_perm,
            "action": func.__name__,
            "action_display_name": action_display_name,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "submit_name": "confirm_action",
        }

        # Display confirmation page
        return modeladmin.render_action_confirmation(request, context)

    return func_wrapper


class DangerousAdminConfirmMixin(AdminConfirmMixin):
    action_confirmation_template = "dangerous_action_confirmation.html"


class TaskResultInline(TabularInline):
    model = TaskResult

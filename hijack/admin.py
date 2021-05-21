from django.conf import settings


class HijackUserAdminMixin(object):
    change_form_template = "admin/hijack/admin_button.html"
    HIJACK_FE_PATH = "/hijack/%s"  # TODO: Change when Nikita will finish FE

    def get_hijack_url(self, object_id):
        return "///" + settings.UI_HOST + self.HIJACK_FE_PATH % object_id

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["hijack_url"] = self.get_hijack_url(object_id)
        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context,
        )

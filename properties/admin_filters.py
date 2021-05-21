from django.contrib import admin
from django.utils.translation import gettext_lazy as _

YES_NO_CHOICE_FILTER = (
    ('yes', _('Yes')),
    ('no', _('No')),
)


class PropertyHasAgentAdminFilter(admin.SimpleListFilter):
    title = _('Has Agent')
    parameter_name = 'agent'

    def lookups(self, request, model_admin):
        return YES_NO_CHOICE_FILTER

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(agent__isnull=False)
        elif self.value() == 'no':
            return queryset.filter(agent__isnull=True)


class PropertyFeaturedAdminFilter(admin.SimpleListFilter):
    title = _('Featured')
    parameter_name = 'featured'

    def lookups(self, request, model_admin):
        return YES_NO_CHOICE_FILTER

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(featured=None)
        elif self.value() == 'no':
            return queryset.filter(featured=None)

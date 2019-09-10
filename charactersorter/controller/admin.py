from django.contrib import admin

from .models import SortRecord

class SortRecordAdmin(admin.ModelAdmin):
    readonly_fields = ('timestamp',)
    list_filter = ('charlist',)

admin.site.register(SortRecord, SortRecordAdmin)

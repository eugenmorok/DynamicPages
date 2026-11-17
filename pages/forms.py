from django import forms
from django.contrib.auth.models import User
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import Page, PageCategory, PageBlock, SiteSetting


class PageForm(forms.ModelForm):
    """Форма для создания/редактирования страниц."""
    content = forms.CharField(
        widget=CKEditor5Widget(config_name='default'),
        required=False,
        label='Содержание',
    )
    excerpt = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False,
        label='Краткое описание',
    )
    meta_keywords = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'через запятую'}),
        required=False,
        label='Meta Keywords',
    )

    class Meta:
        model = Page
        fields = ['title', 'slug', 'category', 'content', 'excerpt',
                  'meta_title', 'meta_description', 'meta_keywords',
                  'featured_image', 'status', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Заголовок страницы'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'URL-адрес (латиницей)'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-control'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = '-- Выберите категорию --'
        if self.instance.pk:
            self.fields['slug'].widget.attrs['readonly'] = True


class PageCategoryForm(forms.ModelForm):
    """Форма для категорий страниц."""
    class Meta:
        model = PageCategory
        fields = ['title', 'slug', 'description', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PageBlockForm(forms.ModelForm):
    """Форма для блоков страницы."""
    content = forms.CharField(
        widget=CKEditor5Widget(config_name='default'),
        required=False,
        label='Содержание',
    )

    class Meta:
        model = PageBlock
        fields = ['title', 'content', 'image', 'ordering']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'ordering': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class SiteSettingForm(forms.ModelForm):
    """Форма для настроек сайта."""
    class Meta:
        model = SiteSetting
        fields = ['value']
        widgets = {
            'value': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class SearchForm(forms.Form):
    """Форма поиска по страницам."""
    q = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск...',
            'aria-label': 'Поиск',
        }),
    )
    category = forms.ModelChoiceField(
        queryset=PageCategory.objects.filter(is_active=True),
        required=False,
        empty_label='Все категории',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

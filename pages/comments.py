"""
Комментарии - формы, вьюхи и templates
"""
from django import forms
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse
from .models import Comment


def _build_comment_context(comment, page):
    """Вспомогательная функция для рендеринга комментария в шаблоне."""
    from django.utils.html import escape
    from django.utils.text import Truncator
    
    return {
        'comment': comment,
        'page': page,
        'replies': comment.get_replies(),
        'replies_count': comment.replies_count(),
        'can_reply': True,
        'truncator': Truncator,
        'escape': escape,
    }


class CommentForm(forms.ModelForm):
    """Форма для добавления комментариев."""
    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
        help_text='Leave this field empty',
    )

    class Meta:
        model = Comment
        fields = ['name', 'email', 'text', 'honeypot']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ваше имя (необязательно)',
                'aria-label': 'Имя',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email (не публикуется)',
                'aria-label': 'Email',
            }),
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Напишите комментарий...',
                'aria-label': 'Комментарий',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.page = kwargs.pop('page', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        honeypot = cleaned_data.get('honeypot')
        if honeypot:
            raise forms.ValidationError('Невозможно отправить пустой комментарий.')
        return cleaned_data


class ReplyForm(forms.ModelForm):
    """Форма для ответов на комментарии."""
    honeypot = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
        help_text='Leave this field empty',
    )

    class Meta:
        model = Comment
        fields = ['text', 'honeypot']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Напишите ответ...',
                'aria-label': 'Ответ',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.parent = kwargs.pop('parent', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        honeypot = cleaned_data.get('honeypot')
        if honeypot:
            raise forms.ValidationError('Невозможно отправить пустой ответ.')
        return cleaned_data

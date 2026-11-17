"""
URL-конфигурация приложения pages.
"""
from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'pages'

urlpatterns = [
    # === Public URLs ===
    path('', views.home, name='home'),
    path('pages/', views.PageListView.as_view(), name='page_list'),
    path('page/<slug:slug>/', views.page_detail, name='page_detail'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),

    # === CRUD URLs ===
    path('create/',
         login_required(views.PageCreateView.as_view()),
         name='page_create'),
    path('pages/<slug:slug>/edit/',
         login_required(views.PageUpdateView.as_view()),
         name='page_update'),
    path('pages/<slug:slug>/delete/',
         login_required(views.PageDeleteView.as_view()),
         name='page_delete'),

    path('blocks/create/<slug:page_slug>/',
         login_required(views.page_block_create),
         name='block_create'),
    path('blocks/<int:pk>/delete/',
         login_required(views.page_block_delete),
         name='block_delete'),

    # Category CRUD
    path('categories/create/',
         login_required(views.CategoryCreateView.as_view()),
         name='category_create'),
    path('categories/<slug:slug>/edit/',
         login_required(views.CategoryUpdateView.as_view()),
         name='category_update'),
    path('categories/<slug:slug>/delete/',
         login_required(views.CategoryDeleteView.as_view()),
         name='category_delete'),

    # === API URLs ===
    path('api/health/', views.health_check, name='api_health'),
    path('api/sitemap/', views.sitemap_xml, name='api_sitemap'),
    path('robots.txt', views.robots_txt, name='robots_txt'),

    # === Comment URLs ===
    path('page/<slug:slug>/comment/', views.add_comment, name='add_comment'),
    path('page/<slug:slug>/comment/<int:comment_pk>/reply/', views.add_reply, name='add_reply'),

    # === Subscription URLs ===
    path('subscribe/', views.subscribe, name='subscribe'),
    path('unsubscribe/<int:uid>/', views.unsubscribe, name='unsubscribe'),

    # === Gallery URLs ===
    path('gallery/', views.gallery_list, name='gallery_list'),
    path('gallery/<int:pk>/', views.gallery_detail, name='gallery_detail'),

    # === Sitemap & robots ===
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
]

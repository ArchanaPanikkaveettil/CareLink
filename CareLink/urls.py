from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.Users.urls')),
    path('dashboard/', include('apps.Dashboard.urls')),
    path('requests/', include('apps.Requests.urls')),
    path('applications/', include('apps.Applications.urls')),
    path('notifications/', include('apps.Notifications.urls')),  
    
    # Add logout URL
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
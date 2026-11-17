"""
REST API rate limiting middleware.
"""
import time
import hashlib
from django.http import HttpResponse
from django.core.cache import cache


DEFAULT_RATE_LIMIT = 60  # requests per minute
DEFAULT_BURST = 10


class SimpleRateLimiter:
    """
    Simple rate limiter using Django cache (Redis).
    Works per client (IP + path hash) to prevent abuse.
    """
    
    def __init__(self, prefix='ratelimit', timeout=60):
        self.prefix = prefix
        self.timeout = timeout
    
    def get_key(self, ip, path):
        """Generate a cache key for the client request."""
        raw = f'{self.prefix}:{ip}:{path}'
        return 'rl:' + hashlib.md5(raw.encode()).hexdigest()
    
    def is_allowed(self, ip, path, limit, burst):
        """Check if request is allowed."""
        key = self.get_key(ip, path)
        now = time.time()
        
        window_start = self.__get_window_start(key, now)
        
        # Check if window exists
        count = cache.get(key, 0)
        
        if count is None:
            count = 1
            cache.set(key, count, self.timeout)
            return {'allowed': True, 'remaining': limit - 1, 'reset': now + self.timeout}
        
        if now - window_start >= self.timeout:
            # Window expired, reset
            cache.set(key, 1, self.timeout)
            return {'allowed': True, 'remaining': limit - 1, 'reset': now + self.timeout}
        
        # Increment count
        new_count = cache.incr(key, 1)
        if new_count > limit:
            return {'allowed': False, 'remaining': 0, 'reset': window_start + self.timeout}
        
        return {'allowed': True, 'remaining': limit - new_count, 'reset': window_start + self.timeout}
    
    def __get_window_start(self, key, now):
        """Get the start of the current window."""
        expires = cache.get(f'{key}_expires', 0)
        if expires == 0:
            cache.set(f'{key}_expires', now + self.timeout, self.timeout)
        return now - self.timeout


class RateLimitMiddleware:
    """
    Rate limiting middleware for API endpoints.
    Default: 60 requests per minute per client IP.
    Can be overridden path-specific.
    """
    
    # Path-specific rate limits
    RATE_LIMITS = {
        '/api/v1/': 120,  # API v1: 120/min
        '/api/v1/pages/': 60,  # Pages: 60/min
        '/api/v1/gallery/': 90,  # Gallery: 90/min
    }
    
    BURST_LIMITS = {
        '/api/v1/': 30,
        '/api/v1/pages/': 20,
        '/api/v1/gallery/': 25,
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.limiter = SimpleRateLimiter(timeout=60)
    
    def __call__(self, request):
        # Skip rate limiting for authenticated users or admin
        if request.user.is_authenticated:
            return self.get_response(request)
        
        # Check path-specific rate limit
        path = request.path
        limit = self._get_rate_limit(path)
        burst = self._get_burst_limit(path)
        
        client_ip = self._get_client_ip(request)
        
        result = self.limiter.is_allowed(client_ip, path, limit, burst)
        
        if not result['allowed']:
            return HttpResponse(
                '{"error": "Rate limit exceeded", "detail": "Too many requests"}',
                status=429,
                content_type='application/json',
            )
        
        # Add rate limit headers
        response = self.get_response(request)
        response['X-RateLimit-Limit'] = str(limit)
        response['X-RateLimit-Remaining'] = str(result['remaining'])
        response['X-RateLimit-Reset'] = str(int(result['reset']))
        response['Retry-After'] = str(int(result['reset'] - time.time()))
        
        return response
    
    def _get_rate_limit(self, path):
        """Get rate limit for a specific path."""
        for prefix, limit in self.RATE_LIMITS.items():
            if path.startswith(prefix):
                return limit
        return DEFAULT_RATE_LIMIT
    
    def _get_burst_limit(self, path):
        """Get burst limit for a specific path."""
        for prefix, limit in self.BURST_LIMITS.items():
            if path.startswith(prefix):
                return limit
        return DEFAULT_BURST
    
    def _get_client_ip(self, request):
        """Get client IP considering proxy headers."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        return request.META.get('REMOTE_ADDR', '127.0.0.1')


# API CORS Middleware
def cors_middleware(get_response):
    """Cors headers for API responses."""
    def middleware(request):
        response = get_response(request)
        response['Access-Control-Allow-Origin'] = "*"
        response['Access-Control-Allow-Headers'] = "Content-Type, Authorization, X-Requested-With"
        response['Access-Control-Allow-Methods'] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        if request.method == "OPTIONS":
            return response
        return response
    return middleware

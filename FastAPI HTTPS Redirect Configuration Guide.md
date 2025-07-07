# FastAPI HTTPS Redirect Configuration Guide

FastAPI HTTPS redirect configuration requires a multi-layered approach combining application middleware, infrastructure setup, and security best practices. This comprehensive guide covers **built-in solutions, custom implementations, reverse proxy configurations, and production deployment strategies** across different platforms and scenarios.

## Built-in FastAPI middleware provides the simplest implementation

FastAPI includes **HTTPSRedirectMiddleware** that automatically redirects HTTP requests to HTTPS with minimal configuration. This middleware enforces secure connections by redirecting all HTTP/WS requests to their HTTPS/WSS equivalents using a 307 status code.

```python
from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app = FastAPI()
app.add_middleware(HTTPSRedirectMiddleware)

@app.get("/")
async def main():
    return {"message": "Hello World"}
```

The built-in middleware has limitations - it cannot specify custom HTTPS ports, lacks conditional logic for development environments, and provides no configuration options. For production applications requiring more control, **TrustedHostMiddleware** complements HTTPS redirects by validating Host headers:

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["example.com", "*.example.com"]
)
```

## Custom middleware implementations offer maximum flexibility

For advanced use cases, custom middleware provides complete control over redirect behavior. **Pure ASGI middleware delivers 20-30% better performance** than BaseHTTPMiddleware under high load:

```python
from fastapi import FastAPI
from starlette.datastructures import URL
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

class PureASGIHTTPSRedirectMiddleware:
    def __init__(self, app: ASGIApp, https_port: int = 443):
        self.app = app
        self.https_port = https_port
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            url = URL(scope=scope)
            if url.scheme == "http":
                redirect_url = url.replace(scheme="https")
                if self.https_port != 443:
                    redirect_url = redirect_url.replace(port=self.https_port)
                response = RedirectResponse(redirect_url, status_code=301)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

app = FastAPI()
app.add_middleware(PureASGIHTTPSRedirectMiddleware)
```

**Environment-aware configuration** prevents development workflow issues:

```python
import os
from fastapi import FastAPI
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app = FastAPI()

# Only enable HTTPS redirect in production
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
```

## Reverse proxy configurations handle SSL termination efficiently

**Nginx provides robust SSL termination** with automatic HTTP to HTTPS redirects. This configuration handles SSL certificates, security headers, and proxy forwarding:

```nginx
# HTTP to HTTPS redirect
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

# HTTPS SSL termination
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Apache configuration** provides similar functionality with different syntax:

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    RewriteEngine on
    RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI} [END,NE,R=permanent]
</VirtualHost>

<VirtualHost *:443>
    ServerName your-domain.com
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/your-domain.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/your-domain.com/privkey.pem
    
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

When using reverse proxies, **configure FastAPI to trust proxy headers**:

```bash
uvicorn main:app --proxy-headers --forwarded-allow-ips '*' --host 0.0.0.0 --port 8000
```

## Security headers and HSTS implementation ensure comprehensive protection

**HTTP Strict Transport Security (HSTS)** forces browsers to use HTTPS for all future requests. The **Secweb library** provides comprehensive security header management:

```python
from fastapi import FastAPI
from Secweb import SecWeb

app = FastAPI()

SecWeb(app=app, Option={
    'hsts': {
        'max-age': 31536000,  # 1 year
        'includeSubDomains': True,
        'preload': True
    },
    'csp': {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'"],
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", "data:", "https:"],
        'connect-src': ["'self'"]
    },
    'xframe': 'DENY',
    'referrer': ['strict-origin-when-cross-origin']
})
```

**Secure cookie configuration** prevents session hijacking:

```python
from fastapi import FastAPI, Response

@app.post("/login")
async def login(response: Response):
    response.set_cookie(
        key="session_token",
        value="secure_token_value",
        httponly=True,        # Prevents XSS access
        secure=True,          # HTTPS only
        samesite="strict",    # CSRF protection
        max_age=3600,         # 1 hour expiry
        path="/"
    )
    return {"message": "Login successful"}
```

## Container and cloud deployment strategies scale from development to production

**Docker Compose with Nginx** provides a complete development environment:

```yaml
version: '3.8'
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl:ro
    depends_on:
      - app
  
  app:
    build: .
    expose:
      - "8000"
    command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

**Kubernetes Ingress** handles HTTPS termination with automatic certificate management:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: fastapi-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: fastapi-tls
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: fastapi-service
            port:
              number: 80
```

**Cloud load balancers** provide managed SSL termination. AWS Application Load Balancer handles HTTPS enforcement automatically when configured with SSL certificates from AWS Certificate Manager. Google Cloud Load Balancer offers similar functionality with automatic certificate provisioning.

## Performance optimization requires careful server and middleware selection

**ASGI server choice significantly impacts performance**. For production deployments, **Gunicorn with Uvicorn workers** provides better process management:

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

**Hypercorn supports HTTP/2 and HTTP/3** for better performance with modern browsers:

```bash
hypercorn main:app --bind 0.0.0.0:8000 --workers 4
```

**Pure ASGI middleware outperforms BaseHTTPMiddleware** by 20-30% under high load. Memory usage is also more efficient, making it essential for production applications handling significant traffic.

## Comprehensive testing validates security implementation

**Automated testing with FastAPI TestClient** ensures redirect functionality:

```python
from fastapi.testclient import TestClient

def test_https_redirect():
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].startswith("https://")

def test_security_headers():
    response = client.get("/", base_url="https://testserver")
    assert "Strict-Transport-Security" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "X-Content-Type-Options" in response.headers
```

**Manual testing commands** validate production deployments:

```bash
# Test HTTP redirect
curl -I -L http://your-domain.com/

# Test HTTPS direct access
curl -I https://your-domain.com/

# Test security headers
curl -I https://your-domain.com/ | grep -E "Strict-Transport-Security|X-Frame-Options"
```

**Security scanner integration** provides continuous monitoring:

```python
def validate_production_security(domain):
    results = {}
    
    # Test HTTPS redirect
    response = requests.get(f"http://{domain}", allow_redirects=False)
    results["https_redirect"] = response.status_code in [301, 302, 307, 308]
    
    # Test security headers
    response = requests.get(f"https://{domain}")
    required_headers = [
        'Strict-Transport-Security',
        'X-Frame-Options',
        'X-Content-Type-Options'
    ]
    results["security_headers"] = all(
        header in response.headers for header in required_headers
    )
    
    return results
```

## Common pitfalls require proactive prevention

**Mixed content issues** occur when HTTPS pages load HTTP resources. Content Security Policy blocks these automatically:

```python
'csp': {
    'default-src': ["'self'"],
    'block-all-mixed-content': []
}
```

**CORS configuration errors** prevent proper cookie handling. Never combine wildcard origins with credentials:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],  # Specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"]
)
```

**Certificate expiration** requires automated monitoring. Let's Encrypt provides free certificates with automatic renewal, while cloud providers offer managed certificate services.

## CDN integration amplifies security and performance

**CloudFlare provides SSL termination** with additional security features. Configure SSL/TLS mode to "Full (Strict)" for end-to-end encryption. **AWS CloudFront** offers similar functionality with integration to AWS Certificate Manager.

**CDN configuration** should enforce HTTPS at the edge:

```json
{
  "ViewerProtocolPolicy": "redirect-to-https",
  "ViewerCertificate": {
    "AcmCertificateArn": "arn:aws:acm:us-east-1:account:certificate/cert-id",
    "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021"
  }
}
```

## Conclusion

Effective FastAPI HTTPS redirect configuration requires combining multiple approaches based on deployment requirements. **Start with built-in middleware for development**, progress to **custom implementations for advanced requirements**, and deploy with **reverse proxy or cloud load balancer SSL termination** for production. **Security headers, proper testing, and monitoring** ensure comprehensive protection against common vulnerabilities.

The key is matching the solution complexity to your specific requirements - simple applications benefit from built-in middleware, while high-traffic production deployments require pure ASGI implementations with infrastructure-level SSL termination. **Performance, security, and maintainability** should guide your choice of implementation strategy.
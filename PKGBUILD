# Maintainer: Will Handley <wh260@cam.ac.uk>
pkgname=mcp-framework
pkgver=0.1.0
pkgrel=1
pkgdesc="A comprehensive MCP toolkit bridging external services and CLI utilities"
arch=('any')
url="https://github.com/handley-lab/mcp-framework"
license=('custom')
depends=(
    'python>=3.10'
    'python-mcp>=1.0.0'
    'python-pydantic>=2.0.0'
    'python-pydantic-settings>=2.0.0'
    'python-google-api-python-client>=2.0.0'
    'python-google-auth-httplib2>=0.1.0'
    'python-google-auth-oauthlib>=0.5.0'
    'python-google-generativeai>=0.8.0'
    'python-openai>=1.0.0'
    'python-pillow>=10.0.0'
)
makedepends=(
    'python-build'
    'python-installer'
    'python-setuptools'
    'python-wheel'
)
checkdepends=(
    'python-pytest>=7.0.0'
    'python-pytest-cov>=4.0.0'
    'python-pytest-asyncio>=0.21.0'
    'python-pytest-mock>=3.0.0'
)
optdepends=(
    'jq: JSON processing for jq tool'
    'vim: Text editing for vim tool'
    'code2prompt: Codebase analysis functionality'
    'python-black: Code formatting for development'
    'python-ruff: Linting for development'
)
source=("$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "$pkgname-$pkgver"
    python -m build --wheel --no-isolation
}

check() {
    cd "$pkgname-$pkgver"
    # Install package in test environment
    python -m installer --destdir="$srcdir/test_install" dist/*.whl
    
    # Add installed package to Python path
    export PYTHONPATH="$srcdir/test_install/usr/lib/python*/site-packages:$PYTHONPATH"
    
    # Run tests with coverage
    python -m pytest tests/ \
        --cov=mcp_framework \
        --cov-report=term-missing \
        --cov-fail-under=95 \
        -v
}

package() {
    cd "$pkgname-$pkgver"
    python -m installer --destdir="$pkgdir" dist/*.whl
    
    
    # Install documentation
    install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
    install -Dm644 CLAUDE.md "$pkgdir/usr/share/doc/$pkgname/CLAUDE.md"
    
    # Install example configuration
    install -Dm644 .env.example "$pkgdir/usr/share/doc/$pkgname/env.example"
}
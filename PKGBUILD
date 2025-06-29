# Maintainer: Will Handley <wh260@cam.ac.uk>
pkgname=python-mcp-handley-lab
pkgver=0.0.0a12
pkgrel=1
pkgdesc="MCP Handley Lab - A comprehensive MCP toolkit for research productivity and lab management"
arch=('any')
url="https://github.com/handley-lab/mcp-handley-lab"
license=('custom')
depends=(
    'python>=3.10'
    'python-mcp>=1.0.0'
    'python-pydantic>=2.0.0'
    'python-pydantic-settings>=2.0.0'
    'python-google-api-python-client>=2.0.0'
    'python-google-auth-httplib2>=0.1.0'
    'python-google-auth-oauthlib>=0.5.0'
    'python-google-genai>=1.0.0'
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
source=()
sha256sums=()

build() {
    cd "$startdir"
    python -m build --wheel --no-isolation
}

#check() {
#    cd "$startdir"
#    
#    # Clean up any previous test installation
#    rm -rf "$srcdir/test_install"
#    
#    # Install package temporarily for testing
#    python -m installer --destdir="$srcdir/test_install" dist/*.whl
#    
#    # Add installed package to Python path
#    export PYTHONPATH="$srcdir/test_install/usr/lib/python$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')/site-packages"
#    
#    # Run tests (skip integration tests that require specific environment)
#    python -m pytest tests/ \
#        --cov=mcp_handley_lab \
#        --cov-report=term-missing \
#        --cov-fail-under=95 \
#        -v \
#        -k "not TestGoogleCalendarIntegration"
#}

package() {
    cd "$startdir"
    python -m installer --destdir="$pkgdir" dist/*.whl
    
    # Install documentation
    install -Dm644 CLAUDE.md "$pkgdir/usr/share/doc/$pkgname/CLAUDE.md"
}

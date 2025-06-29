# Maintainer: Will Handley <wh260@cam.ac.uk>
_pkgname=mcp-handley-lab
pkgname=python-mcp-handley-lab
pkgver=0.0.0a11
pkgrel=3
pkgdesc="MCP Handley Lab - A comprehensive MCP toolkit for research productivity and lab management"
arch=('any')
url="https://github.com/handley-lab/mcp-handley-lab"
license=('custom') # TODO: Replace with actual license when specified
depends=(
    'python'
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
    'jq: JSON processing'
    'vim: Text editing'
    'python-code2prompt: Codebase analysis'
    'python-black: Code formatting'
    'python-ruff: Linting'
)
source=()
sha256sums=()

build() {
    cd "$startdir"
    python -m build --wheel
}

check() {
    cd "$startdir"
    
    # Clean up any previous test installation
    rm -rf "$srcdir/test_install"
    
    # Install package temporarily for testing
    python -m installer --destdir="$srcdir/test_install" dist/*.whl
    
    # Add installed package to Python path
    export PYTHONPATH="$srcdir/test_install/usr/lib/python$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')/site-packages"
    
    # Run tests (skip integration tests that require specific environment)
    python -m pytest tests/ \
        --cov=mcp_handley_lab \
        --cov-report=term-missing \
        --cov-fail-under=95 \
        -v \
        -k "not integration"
}

package() {
    cd "$startdir"
    python -m installer --destdir="$pkgdir" dist/*.whl
    
    # Install documentation
    install -Dm644 CLAUDE.md "$pkgdir/usr/share/doc/$pkgname/CLAUDE.md"
}

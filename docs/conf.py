from datetime import date
from os import mkdir, path

import guzzle_sphinx_theme

from pyinfra import __version__, local


copyright = 'Nick Barrett {0} — pyinfra v{1}'.format(
    date.today().year,
    __version__,
)

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.autosectionlabel',
    'guzzle_sphinx_theme',
]
autosectionlabel_prefix_document = True

source_suffix = ['.rst', '.md']
source_parsers = {
    '.md': 'recommonmark.parser.CommonMarkParser',
}

master_doc = 'index'
project = 'pyinfra'
author = 'Fizzadar'
version = 'develop'
pygments_style = 'monokai'

# Theme style override
html_short_title = 'Home'
html_theme = 'guzzle_sphinx_theme'
html_theme_path = guzzle_sphinx_theme.html_theme_path()
html_static_path = ['static']

templates_path = ['templates']

html_favicon = 'static/logo_small.png'

html_sidebars = {
    '**': ['pyinfra_sidebar.html', 'searchbox.html'],
}

exclude_patterns = [
    '_deploy_globals.rst',
]


def setup(app):
    this_dir = path.dirname(path.realpath(__file__))
    scripts_dir = path.abspath(path.join(this_dir, '..', 'scripts'))

    for auto_docs_name in ('modules', 'facts'):
        auto_docs_path = path.join(this_dir, auto_docs_name)
        if not path.exists(auto_docs_path):
            mkdir(auto_docs_path)

    local.shell((
        'python {0}/generate_global_kwargs_doc.py'.format(scripts_dir),
        'python {0}/generate_facts_docs.py'.format(scripts_dir),
        'python {0}/generate_modules_docs.py'.format(scripts_dir),
    ))

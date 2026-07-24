import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path('app/reasonreport').resolve()))
from scripts.externalize_inline_scripts import externalize


class JupyterLiteCspBuildTest(unittest.TestCase):
    def test_development_compose_enables_both_reloaders(self):
        base_compose = Path('docker-compose.yml').read_text()
        compose = Path('docker-compose.dev.yml').read_text()
        script = Path('scripts/dev_server.sh').read_text()

        self.assertIn("version: '3'", base_compose)
        self.assertIn("version: '3'", compose)
        self.assertIn('FLASK_DEBUG: "true"', compose)
        self.assertNotIn('./app:/app', compose)
        self.assertEqual(base_compose.count('./app:/app'), 1)
        self.assertIn('flask run --debug', script)
        self.assertIn('/build/flask_extension/src', compose)
        self.assertIn('npm run build:prod', script)
        self.assertIn('jupyter lite build', script)

    def test_docker_build_bundles_pyodide_for_same_origin_loading(self):
        dockerfile = Path('Dockerfile').read_text(encoding='utf-8')

        self.assertIn('pyodide-0.27.6.tar.bz2', dockerfile)
        self.assertIn('/opt/jupyterlite/static/pyodide/pyodide.js', dockerfile)
        self.assertIn('"pyodideUrl": "./static/pyodide/pyodide.js"', dockerfile)
        self.assertIn('comm==0.2.2', dockerfile)
        self.assertIn('--piplite-wheels=/build/piplite-wheels', dockerfile)
        self.assertIn('/opt/jupyterlite/api/pypi/all.json', dockerfile)

    def test_externalizes_only_executable_inline_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            html_path = Path(directory, "index.html")
            html_path.write_text(
                """<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self' data:\">
<script type=\"application/json\">{\"key\": true}</script>
<script src=\"./existing.js\"></script>
<script type=\"module\">console.log('module')</script>
<script>console.log('classic')</script>""",
                encoding="utf-8",
            )

            self.assertEqual(externalize(html_path), 2)
            updated = html_path.read_text(encoding="utf-8")
            self.assertIn('<script type="application/json">', updated)
            self.assertIn('src="./existing.js"', updated)
            self.assertIn('src="./csp-inline-1.js"', updated)
            self.assertIn('src="./csp-inline-2.js"', updated)
            self.assertIn("script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'", updated)
            self.assertIn("style-src 'self' 'unsafe-inline'", updated)
            self.assertNotIn('cdn.jsdelivr.net', updated)
            self.assertIn(
                "connect-src 'self' https://pypi.org https://files.pythonhosted.org",
                updated,
            )
            self.assertNotIn("content=\"default-src 'self' data:\"", updated)
            self.assertEqual(
                Path(directory, "csp-inline-1.js").read_text(encoding="utf-8"),
                "console.log('module')\n",
            )

    def test_editor_templates_have_no_executable_inline_code(self):
        templates = Path("app/reasonreport/templates")
        for name in ("base.html", "edit.html", "index.html"):
            content = templates.joinpath(name).read_text(encoding="utf-8")
            self.assertNotIn("<style", content, name)
            self.assertNotIn("onclick=", content, name)
        self.assertNotIn("<script>", templates.joinpath("edit.html").read_text())

    def test_header_uses_green_palette(self):
        styles = Path('app/reasonreport/static/css/styles.css').read_text()

        self.assertIn('background-color: #dff3e4', styles)
        self.assertIn('color: #176b3a', styles)

    def test_default_browser_title_uses_product_name(self):
        template = Path('app/reasonreport/templates/base.html').read_text()

        self.assertIn('title if title else "Reason Report"', template)
        self.assertNotIn('Flask App', template)

    def test_publish_errors_reenable_publish_button(self):
        editor_script = Path('app/reasonreport/static/js/edit.js').read_text()

        self.assertIn('function finishPublishing()', editor_script)
        self.assertIn('async function publishedSlug(message)', editor_script)
        publish_result = editor_script.index(
            "message.msgtype === 'publish-result'"
        )
        missing_slug = editor_script.index('if (!slug)', publish_result)
        reset = editor_script.index('finishPublishing();', publish_result)
        self.assertLess(reset, missing_slug)

    def test_editor_requests_storage_cleanup_when_closed(self):
        editor_script = Path('app/reasonreport/static/js/edit.js').read_text()
        extension = Path('flask_extension/src/index.ts').read_text()

        self.assertIn("send({ msgtype: 'cleanup', documentId })", editor_script)
        self.assertIn("msgtype: 'cleanup-result'", extension)
        self.assertIn('window.localStorage.clear()', extension)
        self.assertIn('await contents.delete(entry.path)', extension)

    def test_missing_contents_manifest_returns_empty_drive(self):
        import app as reasonreport_app

        with tempfile.TemporaryDirectory() as directory, patch.object(
            reasonreport_app, 'JUPYTERLITE_PATH', directory
        ):
            response = reasonreport_app.app.test_client().get(
                '/jupyterlite/api/contents/all.json'
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['content'], [])
        self.assertEqual(response.json['type'], 'directory')
        self.assertEqual(
            response.headers['X-ReasonReport-JupyterLite-Fallback'],
            'empty-contents',
        )


if __name__ == "__main__":
    unittest.main()

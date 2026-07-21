import tempfile
import unittest
from pathlib import Path

from scripts.externalize_inline_scripts import externalize


class JupyterLiteCspBuildTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

"""Real document extraction and OCR acceptance. Usage: python test_indexed_search.py PACKAGE.

Requires Ghostscript and ImageMagick for disposable fixtures. No real user files are indexed.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

helper = str(Path(sys.argv[1]) / 'bin/hp-os-search')
with tempfile.TemporaryDirectory(prefix='hp-search-extraction-') as directory:
    root = Path(directory)
    docs = root / 'Documents'; docs.mkdir()
    (root / 'runtime').mkdir(mode=0o700)
    env = dict(os.environ, HOME=str(root), XDG_STATE_HOME=str(root / 'state'), XDG_RUNTIME_DIR=str(root / 'runtime'))
    def run(args):
        return subprocess.run(args, env=env, capture_output=True, text=True, check=True, timeout=120)
    ps = root / 'fixture.ps'
    ps.write_text('%!PS\n/Helvetica findfont 28 scalefont setfont\n72 720 moveto (quartzpdfcontent) show\nshowpage\n')
    run(['gs', '-q', '-dBATCH', '-dNOPAUSE', '-sDEVICE=pdfwrite', '-sOutputFile=' + str(docs / 'document.pdf'), str(ps)])
    with zipfile.ZipFile(docs / 'letter.docx', 'w') as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>cobaltwordcontent</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(docs / 'slides.pptx', 'w') as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>')
        z.writestr('ppt/slides/slide1.xml', '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><a:t>amberpresentationcontent</a:t></p:cSld></p:sld>')
    with zipfile.ZipFile(docs / 'table.xlsx', 'w') as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
        z.writestr('xl/sharedStrings.xml', '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>violetspreadsheetcontent</t></si></sst>')
    run(['magick', '-size', '1200x180', 'xc:white', '-font', 'DejaVu-Sans', '-pointsize', '54', '-fill', 'black', '-gravity', 'center', '-annotate', '0', 'SAPPHIRE OCR CONTENT', str(docs / 'picture.png')])
    run(['magick', str(docs / 'picture.png'), str(docs / 'scan.pdf')])
    run([helper, '--index'])
    state = json.loads(run([helper, '--status']).stdout)
    assert state['state'] == 'ready', (state, (root / 'state/hp-os/search/index.log').read_text())
    for query, filename in [('quartzpdfcontent', 'document.pdf'), ('cobaltwordcontent', 'letter.docx'), ('amberpresentationcontent', 'slides.pptx'), ('violetspreadsheetcontent', 'table.xlsx'), ('sapphire', 'picture.png'), ('sapphire', 'scan.pdf')]:
        result = json.loads(run([helper, query]).stdout)
        assert filename in [item['name'] for item in result['results']], (query, result, (root / 'state/hp-os/search/index.log').read_text())
        print('PASS', filename, 'content extraction')
    (docs / 'document.pdf').unlink()
    assert not json.loads(run([helper, 'quartzpdfcontent']).stdout)['results'], 'Deleted indexed files must be excluded'
    print('PASS deleted-file exclusion')

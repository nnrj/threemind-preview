// Source-only UI catalogue audit. Does not read data/, .env or running projects.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('..', import.meta.url));
const require = createRequire(new URL('../threemind-ui/package.json', import.meta.url));
const ts = require('typescript');
const ui = path.join(root, 'threemind-ui/src/v2');
const englishFile = path.join(ui, 'locales/en.ts');
const catalogue = new Map();
const duplicates = [];
function readFile(file, visited = new Set()) {
  if (visited.has(file)) throw new Error('Cyclic translation import');
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
  const imports = new Map();
  for (const node of source.statements) {
    if (ts.isImportDeclaration(node) && node.importClause?.name && ts.isStringLiteral(node.moduleSpecifier)) {
      const target = path.resolve(path.dirname(file), node.moduleSpecifier.text + '.ts');
      if (!target.startsWith(path.dirname(englishFile) + path.sep)) throw new Error('Translation import outside locale directory');
      imports.set(node.importClause.name.text, target);
    }
  }
  const own = new Set();
  function read(node) {
  if (ts.isVariableDeclaration(node) && node.initializer && ts.isObjectLiteralExpression(node.initializer)) {
    for (const entry of node.initializer.properties) {
      if (ts.isSpreadAssignment(entry) && ts.isIdentifier(entry.expression) && imports.has(entry.expression.text)) {
        readFile(imports.get(entry.expression.text), new Set([...visited, file]));
        continue;
      }
      if (!ts.isPropertyAssignment(entry) || !(ts.isStringLiteral(entry.name) || ts.isIdentifier(entry.name)) || !ts.isStringLiteral(entry.initializer)) throw new Error('Expected a plain text translation catalogue');
      const key = entry.name.text;
      if (own.has(key)) duplicates.push(key);
      own.add(key);
      catalogue.set(key, entry.initializer.text);
    }
  }
  ts.forEachChild(node, read);
  }
  read(source);
}
readFile(englishFile);
const missing = [], untranslated = {};
const placeholders = value => [...new Set([...value.matchAll(/\{([a-zA-Z_][a-zA-Z_0-9]*)\}/g)].map(m => m[1]))].sort().join(',');
const invalidPlaceholders = [...catalogue].filter(([key, value]) => placeholders(key) !== placeholders(value)).map(([source]) => source);
let metadata;
if (process.argv.includes('--metadata-stdin')) {
  const source = JSON.parse(fs.readFileSync(0, 'utf8').replace(/^\uFEFF/,''));
  metadata = {parameters: source.parameters, adapters: source.adapters, commands: source.commands, texts: source.texts.length};
  for (const key of source.texts) if (/[\u3400-\u9fff]/.test(key) && !catalogue.has(key.trim().replace(/\s+/g,' '))) missing.push({file: 'runtime-metadata',source:key});
}
let references = 0, dynamicReferences = 0;
for (const file of fs.readdirSync(ui).filter(f => /\.tsx?$/.test(f))) {
  const code = fs.readFileSync(path.join(ui, file), 'utf8');
  const tree = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, file.endsWith('tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  function visit(node) {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'messageKeys') {
      if (!ts.isObjectLiteralExpression(node.arguments[0])) throw new Error('messageKeys requires a literal source-owned map');
      for (const property of node.arguments[0].properties) {
        if (!ts.isPropertyAssignment(property) || !ts.isStringLiteral(property.initializer)) throw new Error('messageKeys values must be text literals');
        const key = property.initializer.text.trim().replace(/\s+/g, ' ');
        dynamicReferences++;
        if (!catalogue.has(key)) missing.push({file, source: key, line: tree.getLineAndCharacterOfPosition(property.getStart()).line + 1});
      }
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 't' && ts.isStringLiteral(node.arguments[0])) {
      const key = node.arguments[0].text.trim().replace(/\s+/g, ' ');
      references++;
      if (!catalogue.has(key)) missing.push({file, source: key, line: tree.getLineAndCharacterOfPosition(node.getStart()).line + 1});
    }
    if ((ts.isJsxText(node) || ts.isStringLiteral(node) && ts.isJsxAttribute(node.parent) && ['label','title','description','hint','detail','aria-label','placeholder'].includes(node.parent.name.text)) && /[\u3400-\u9fff]/.test(node.text)) untranslated[file] = (untranslated[file] ?? 0) + 1;
    ts.forEachChild(node, visit);
  }
  visit(tree);
}
console.log(JSON.stringify({catalogue: catalogue.size, literalReferences: references, dynamicReferences, metadata, duplicates, invalidPlaceholders, missing, remainingDirectDisplayLiterals: untranslated}, null, 2));
if (duplicates.length || invalidPlaceholders.length || missing.length || process.argv.includes('--complete') && Object.keys(untranslated).length) process.exitCode = 1;

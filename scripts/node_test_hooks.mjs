// Module hooks for the TypeScript tests of the client's pure modules
// (tests/web/), run by Node's own runner:
//
//   node --import ./scripts/node_test_hooks.mjs --test "tests/web/**/*.test.ts"
//
// Node strips the types itself (22.18 or later; CI takes lts/*). The hooks
// give Node the two imports Vite allows and Node does not: a relative import
// without its extension (`./activityFeed`) and a JSON import without its
// attribute (`../i18n/fr.json`). `svelte/reactivity` needs nothing: Node finds
// it in web/node_modules and takes Svelte's server build.
//
// Not handled: an extensionless import of a file whose name holds a dot
// (`./room.types`) or of a folder's index (`./dir`); write the full path.

import { existsSync } from 'node:fs'
// A namespace import, so that a Node without registerHooks reaches the check
// below instead of failing on the import itself.
import * as nodeModule from 'node:module'
import { fileURLToPath } from 'node:url'

if (!process.features.typescript || typeof nodeModule.registerHooks !== 'function') {
  console.error(
    `FAIL: the TypeScript tests need Node 22.18 or later with type stripping on (CI: lts/*); found ${process.version}.`,
  )
  process.exit(1)
}

const EXTENSION = /\.[a-z]+$/i

nodeModule.registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.endsWith('.json')) {
      const resolved = nextResolve(specifier, context)
      return {
        ...resolved,
        importAttributes: { ...context.importAttributes, type: 'json' },
      }
    }
    const relative = specifier.startsWith('./') || specifier.startsWith('../')
    if (relative && context.parentURL && !EXTENSION.test(specifier)) {
      const candidate = new URL(`${specifier}.ts`, context.parentURL)
      if (existsSync(fileURLToPath(candidate))) {
        const resolved = nextResolve(candidate.href, context)
        return { ...resolved, format: 'module-typescript' }
      }
    }
    return nextResolve(specifier, context)
  },
})

import '@testing-library/jest-dom'
import { beforeEach } from 'vitest'

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

if (typeof Element !== 'undefined' && !Element.prototype.scrollTo) {
  Element.prototype.scrollTo = function () {}
}

// Node 22+ 在 globalThis 上注册了 localStorage/sessionStorage 访问器（未启用
// --experimental-webstorage 时取值为 undefined）；而在 Node 26 + vitest 的 jsdom 环境里
// window.localStorage 同样是 undefined，于是测试里裸用 localStorage.clear() 会崩：
//   TypeError: Cannot read properties of undefined (reading 'clear')
// 浏览器/jsdom 正常都会提供 Web Storage，这里在缺失时补一个内存实现兜底
// （只实现本项目用到的 API：getItem/setItem/removeItem/clear，另附 length/key）。
function createMemoryStorage() {
  const data = new Map()
  return {
    get length() {
      return data.size
    },
    key(i) {
      return Array.from(data.keys())[i] ?? null
    },
    getItem(k) {
      return data.has(String(k)) ? data.get(String(k)) : null
    },
    setItem(k, v) {
      data.set(String(k), String(v))
    },
    removeItem(k) {
      data.delete(String(k))
    },
    clear() {
      data.clear()
    },
  }
}

for (const storageName of ['localStorage', 'sessionStorage']) {
  let current
  try {
    current = globalThis[storageName]
  } catch {
    current = undefined
  }
  if (!current) {
    Object.defineProperty(globalThis, storageName, {
      value: createMemoryStorage(),
      configurable: true,
      writable: true,
    })
  }
}

// 兜底实现会被同一 worker 内的多个测试文件共用（vitest.config.js 里 isolate: false），
// 不清理会让某个文件写入的标记泄漏到别的文件（实测 TrialExpiredModal 因此从绿变红）。
// jsdom 真实的 Web Storage 是每个测试文件独立环境，这里用 beforeEach 清空还原同样的隔离语义。
beforeEach(() => {
  try {
    globalThis.localStorage?.clear()
  } catch {
    /* ignore */
  }
  try {
    globalThis.sessionStorage?.clear()
  } catch {
    /* ignore */
  }
})

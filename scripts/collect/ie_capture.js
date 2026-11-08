/**
 * ie_capture.js — IE 岗位数据采集脚本（swt-screener 配套）
 *
 * 用法（方式 B · 控制台粘贴）：
 *   1. 用你自己的账号登录 IE（app.interexchange.org）
 *   2. 打开浏览器开发者工具（F12）→ Console，粘贴本文件全部代码，回车
 *   3. 页面右下角出现「SWT 采集」按钮 = 挂钩成功
 *   4. 正常浏览：先看岗位列表页，再逐个点开你关心的岗位详情页
 *      （列表接口和详情接口的响应会被自动捕获，SPA 内跳转不丢数据）
 *   5. 浏览完后点按钮 → 自动下载 swt_capture_<日期>.json
 *
 * 注意：
 *   - 只在你自己已登录的 IE 会话里使用；采集的就是你本人能看到的内容
 *   - 如果刷新了页面，挂钩会失效，重新粘贴一次即可
 *   - 发现账号/站点异常提示，立即停止采集
 *   - 采集结果交给 scripts/collect/prefilter.py 粗筛 → collect_to_input.py 合并
 */
(function () {
  "use strict";
  if (window.__swtCapture) {
    console.log("[swt-capture] 已挂钩，无需重复粘贴。已采", Object.keys(window.__swtCapture.list).length,
      "张卡 /", Object.keys(window.__swtCapture.details).length, "个详情");
    return;
  }

  var store = { list: {}, details: {} };

  // ---------- 识别 IE 数据 ----------
  function looksLikeList(d) {
    return Array.isArray(d) && d.length > 0 &&
      d.some(function (x) { return x && typeof x === "object" && typeof x.id === "string" && x.id.indexOf("job_listing_") === 0; });
  }
  function looksLikeDetail(d) {
    return d && typeof d === "object" && !Array.isArray(d) &&
      Array.isArray(d.pairs) &&
      d.pairs.some(function (p) { return Array.isArray(p) && p[0] === "Start"; });
  }
  function unwrap(d) {
    // 兼容 {"value": "<json字符串>"} 的包裹形式
    for (var i = 0; i < 3; i++) {
      if (d && typeof d === "object" && typeof d.value === "string") {
        try { d = JSON.parse(d.value); } catch (e) { break; }
      } else break;
    }
    return d;
  }
  function ingest(d) {
    d = unwrap(d);
    if (looksLikeList(d)) {
      var before = Object.keys(store.list).length;
      d.forEach(function (c) { if (c && c.id) store.list[c.id] = c; });
      var added = Object.keys(store.list).length - before;
      if (added) console.log("[swt-capture] 列表 +" + added + "，累计 " + Object.keys(store.list).length + " 张卡");
    } else if (looksLikeDetail(d)) {
      var u = d.url || "";
      if (u && !store.details[u]) {
        store.details[u] = d;
        console.log("[swt-capture] 详情 +1（" + u + "），累计 " + Object.keys(store.details).length + " 个详情");
      }
    }
  }

  // ---------- 挂钩 fetch ----------
  var origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function () {
      var p = origFetch.apply(this, arguments);
      try {
        p.then(function (resp) {
          if (!resp || typeof resp.clone !== "function") return;
          resp.clone().text().then(function (txt) {
            try { ingest(JSON.parse(txt)); } catch (e) { /* 非 JSON 响应，跳过 */ }
          }).catch(function () {});
        }).catch(function () {});
      } catch (e) {}
      return p;
    };
  }

  // ---------- 挂钩 XHR ----------
  var origOpen = XMLHttpRequest.prototype.open;
  var origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__swtUrl = u; return origOpen.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function () {
    var xhr = this;
    try {
      xhr.addEventListener("load", function () {
        try { ingest(JSON.parse(xhr.responseText)); } catch (e) { /* 非 JSON，跳过 */ }
      });
    } catch (e) {}
    return origSend.apply(this, arguments);
  };

  // ---------- 导出按钮 ----------
  var btn = document.createElement("button");
  btn.id = "__swt_capture_btn";
  btn.textContent = "SWT 采集";
  btn.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:999999;" +
    "background:#8839ef;color:#fff;border:none;border-radius:999px;padding:10px 18px;" +
    "font-size:14px;font-weight:600;cursor:pointer;box-shadow:0 4px 14px rgba(136,57,239,.45);";
  btn.addEventListener("mouseenter", function () { renderBtn(); });
  btn.addEventListener("click", function () {
    var out = {
      app: "swt-screener",
      captured_at: new Date().toISOString(),
      base_url: location.origin,
      list: Object.keys(store.list).map(function (k) { return store.list[k]; }),
      details: Object.keys(store.details).map(function (k) { return store.details[k]; })
    };
    var blob = new Blob([JSON.stringify(out, null, 1)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "swt_capture_" + new Date().toISOString().slice(0, 10) + ".json";
    document.body.appendChild(a); a.click(); a.remove();
    console.log("[swt-capture] 已导出：", a.download, "（列表", out.list.length, "张 / 详情", out.details.length, "个）");
  });
  function renderBtn() {
    btn.textContent = "SWT 采集 · 卡 " + Object.keys(store.list).length + " / 详情 " + Object.keys(store.details).length + " · 点我导出";
  }
  document.body.appendChild(btn);

  window.__swtCapture = store;
  console.log("%c[swt-capture] 挂钩成功", "color:#8839ef;font-weight:bold");
  console.log("  1) 刷新或打开 IE 岗位列表页（列表接口响应会被自动捕获）");
  console.log("  2) 逐个点开你关心的岗位详情页（详情接口响应会被自动捕获）");
  console.log("  3) 浏览完点右下角按钮导出 swt_capture_<日期>.json");
})();

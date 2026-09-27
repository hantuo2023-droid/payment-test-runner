"use client";
/* Screenshots are authenticated evidence URLs and should not use Next image caching. */
/* eslint-disable @next/next/no-img-element */
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Circle,
  CreditCard,
  Database,
  Download,
  Globe,
  History,
  Home,
  Layers,
  LogOut,
  Play,
  Plus,
  RefreshCw,
  Settings,
  ShieldCheck,
  Square,
  Trash2,
  Upload,
  Users,
  X,
} from "lucide-react";

const NAV = [
  ["首页", Home],
  ["账号", Users],
  ["测试数据", CreditCard],
  ["运行记录", History],
  ["任务", Layers],
  ["设置", Settings],
];
async function api(path, method = "GET", body) {
  const r = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-PTR-Client": "web" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let d;
    try {
      d = await r.json();
    } catch {
      d = { detail: "服务连接失败" };
    }
    const e = new Error(
      typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail),
    );
    e.status = r.status;
    throw e;
  }
  return r.json();
}
function Field({ label, help, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      <small>{help}</small>
    </label>
  );
}
function Badge({ value }) {
  return <span className={"badge " + value}>{value || "—"}</span>;
}
function Panel({ title, number, action, children, className = "" }) {
  return (
    <section className={"panel " + className}>
      <div className="panel-heading">
        <div className="heading-left">
          {number && <span className="number">{number}</span>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function Empty({ text }) {
  return (
    <div className="empty">
      <Database />
      <div>{text}</div>
    </div>
  );
}
function time(value) {
  return value
    ? new Date(value).toLocaleString("zh-CN", { hour12: false })
    : "—";
}
function bytes(value) {
  return value > 1048576
    ? (value / 1048576).toFixed(1) + " MB"
    : (value / 1024).toFixed(1) + " KB";
}
function Modal({ title, description, onClose, children, error, notice }) {
  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal">
        <div className="split">
          <h2>{title}</h2>
          <button className="ghost" onClick={onClose} aria-label="关闭">
            <X />
          </button>
        </div>
        <p className="subtitle">{description}</p>
        {error && <div className="error-banner">{error}</div>}
        {notice && <div className="success-banner">{notice}</div>}
        {children}
      </div>
    </div>
  );
}

export default function App() {
  const runSignature = useRef("");
  const [logged, setLogged] = useState(false),
    [boot, setBoot] = useState(true),
    [password, setPassword] = useState(""),
    [page, setPage] = useState("首页");
  const [accounts, setAccounts] = useState([]),
    [cards, setCards] = useState([]),
    [tasks, setTasks] = useState([]),
    [networks, setNetworks] = useState([]),
    [runs, setRuns] = useState([]),
    [health, setHealth] = useState({}),
    [stats, setStats] = useState({});
  const [aids, setAids] = useState([]),
    [cids, setCids] = useState([]),
    [taskId, setTaskId] = useState(1),
    [networkId, setNetworkId] = useState(1),
    [check, setCheck] = useState(null),
    [checking, setChecking] = useState(false),
    [working, setWorking] = useState(false);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [modal, setModal] = useState(null),
    [text, setText] = useState(""),
    [preview, setPreview] = useState(null),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState(""),
    [date, setDate] = useState("");
  const [runId, setRunId] = useState(null),
    [run, setRun] = useState(null),
    [resultIds, setResultIds] = useState([]),
    [runIds, setRunIds] = useState([]),
    [logs, setLogs] = useState(""),
    [liveLogs, setLiveLogs] = useState([]),
    [editor, setEditor] = useState({}),
    [days, setDays] = useState(30);
  const currentTask = tasks.find((t) => t.id === taskId),
    binding = currentTask?.environment !== "Production";
  const report = useCallback((e) => {
    setError(e.message);
    if (e.status === 401) setLogged(false);
  }, []);
  const refresh = useCallback(async () => {
    try {
      const [a, c, t, n, r, h, s] = await Promise.all(
        [
          "/accounts",
          "/cards",
          "/tasks",
          "/networks",
          "/runs",
          "/health",
          "/data-management",
        ].map((p) => api(p)),
      );
      setAccounts(a);
      setCards(c);
      setCids((selected) =>
        selected.filter((id) => c.some((item) => item.id === id && !item.used)),
      );
      setTasks(t);
      setNetworks(n);
      setRuns(r);
      runSignature.current = JSON.stringify(
        r.map((item) => [item.id, item.status]),
      );
      setHealth(h);
      setStats(s);
      setLogged(true);
    } catch (e) {
      report(e);
    } finally {
      setBoot(false);
    }
  }, [report]);
  useEffect(() => {
    const id = setTimeout(() => {
      refresh();
    }, 0);
    return () => clearTimeout(id);
  }, [refresh]);
  useEffect(() => {
    if (!logged) return;
    const id = setInterval(() => {
      api("/health").then(setHealth).catch(report);
      api("/runs")
        .then((items) => {
          setRuns(items);
          const signature = JSON.stringify(
            items.map((item) => [item.id, item.status]),
          );
          if (signature !== runSignature.current) {
            runSignature.current = signature;
            setCheck(null);
            refresh();
          }
        })
        .catch(report);
      if (runId) {
        api("/runs/" + runId)
          .then(setRun)
          .catch(report);
        api("/runs/" + runId + "/logs")
          .then(setLiveLogs)
          .catch(report);
      }
    }, 1500);
    return () => clearInterval(id);
  }, [logged, runId, report, refresh]);
  useEffect(() => {
    if (!check?.ready) return;
    const timer = setTimeout(() => setCheck(null), 115000);
    return () => clearTimeout(timer);
  }, [check]);
  const act = async (fn) => {
    setError("");
    setWorking(true);
    try {
      await fn();
    } catch (e) {
      report(e);
    } finally {
      setWorking(false);
    }
  };
  const changePage = (p) => {
    setPage(p);
    setQuery("");
    setFilter("");
    setDate("");
  };
  const toggle = (id, ids, setter) => {
    setter(ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
    setCheck(null);
  };
  const openImport = (kind) => {
    setText("");
    setPreview(null);
    setModal({ type: "import", kind });
  };
  const openRun = async (id) => {
    setRunId(id);
    setRun(await api("/runs/" + id));
    setResultIds([]);
    changePage("运行记录");
  };
  const plan = () => ({
    task_id: taskId,
    network_id: networkId,
    account_ids: aids,
    card_ids: binding ? cids : [],
  });
  const doCheck = async () => {
    setChecking(true);
    try {
      setCheck(await api("/preflight", "POST", plan()));
    } finally {
      setChecking(false);
    }
  };
  const remove = (kind, ids, all = false) => {
    if (
      window.confirm(
        all
          ? "确认清空全部数据？此操作无法撤销。"
          : "确认删除选中的数据及关联文件？此操作无法撤销。",
      )
    )
      act(async () => {
        await api("/" + kind + "/delete", "POST", {
          ids,
          all,
          confirmed: true,
        });
        setAids([]);
        setCids([]);
        setRunIds([]);
        setCheck(null);
        await refresh();
        setNotice("数据已删除");
      });
  };
  const close = () => setModal(null);
  const download = (p) => {
    const a = document.createElement("a");
    a.href = "/api" + p;
    a.download = "";
    a.click();
  };
  const fields = (label, help, key, type = "text") => (
    <Field label={label} help={help}>
      <input
        type={type}
        value={editor[key] ?? ""}
        onChange={(e) => setEditor({ ...editor, [key]: e.target.value })}
      />
    </Field>
  );
  const filtered = (list) =>
    list.filter((x) =>
      JSON.stringify(x).toLowerCase().includes(query.toLowerCase()),
    );
  const live = runs.find((r) => ["RUNNING", "QUEUED"].includes(r.status));
  if (boot)
    return (
      <div className="login">
        <p>正在连接工作台…</p>
      </div>
    );
  if (!logged)
    return (
      <div className="login">
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              await api("/auth/login", "POST", { password });
              setPassword("");
              await refresh();
              setError("");
            });
          }}
        >
          <div className="brand">
            <span className="brand-icon">
              <Activity />
            </span>
            <span>Payment Test Runner</span>
          </div>
          <h1>登录你的工作台</h1>
          <p className="subtitle">真实浏览器执行。每一步，都有据可查。</p>
          {error && <p className="error-banner">{error}</p>}
          <Field
            label="管理员密码"
            help="用途：登录管理后台 · 必填 · 格式：初始化时设置的至少 12 位密码；请勿输入测试账号密码。"
          >
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <button className="primary start" disabled={working}>
            登录 <ArrowRight />
          </button>
          <p className="hint">
            首次使用：在项目终端运行{" "}
            <code>python -m backend.cli init-admin</code> 初始化管理员。
          </p>
        </form>
      </div>
    );
  return (
    <>
      <aside>
        <div className="brand">
          <span className="brand-icon">
            <Activity />
          </span>
          <span className="brand-text">
            Payment Runner<small>TESTING WORKSPACE</small>
          </span>
        </div>
        <div className="nav-title">WORKSPACE</div>
        <nav>
          {NAV.map(([label, Icon]) => (
            <button
              key={label}
              className={page === label ? "active" : ""}
              onClick={() => changePage(label)}
              title={label}
            >
              <Icon />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div>
            <span className="dot" />
            LIVE 工作空间
          </div>
          <p>简单测试，清晰结果。</p>
          <div style={{ fontSize: 10 }}>
            VERSION {health.version || "0.1.0"}
          </div>
        </div>
      </aside>
      <div className="shell">
        <header>
          <span>
            工作空间{" "}
            <ChevronRight
              style={{ width: 12, verticalAlign: "middle", margin: "0 12px" }}
            />{" "}
            {page}
          </span>
          <div className="header-right">
            <span className="live">
              <span className="dot" />
              LIVE
            </span>
            <span>本地测试工作台</span>
            <span className="avatar">AD</span>
            <button
              className="ghost"
              title="退出登录"
              onClick={() =>
                act(async () => {
                  await api("/auth/logout", "POST");
                  setLogged(false);
                })
              }
            >
              <LogOut />
            </button>
          </div>
        </header>
        <main>
          {error && (
            <div className="error-banner">
              <span>{error}</span>
              <button
                className="ghost"
                onClick={() => setError("")}
                aria-label="关闭错误"
              >
                <X />
              </button>
            </div>
          )}
          {notice && (
            <div className="success-banner" onClick={() => setNotice("")}>
              {notice}
            </div>
          )}
          {page === "首页" && (
            <>
              <div className="title-row">
                <div>
                  <h1>
                    Payment Test Runner{" "}
                    <span className="version">v{health.version}</span>
                  </h1>
                  <p className="subtitle">
                    从准备到结果，让每一次测试都简单有序。
                  </p>
                </div>
                <button onClick={() => act(refresh)}>
                  <RefreshCw />
                  刷新状态
                </button>
              </div>
              <div className="system-strip">
                <strong>系统状态</strong>
                {[
                  ["Backend", health.backend],
                  ["Database", health.database],
                  ["Worker", health.worker],
                  ["Chromium", check?.chromium],
                  ["Network", check?.connected],
                  ["Disk", health.disk],
                ].map(([n, ok]) => (
                  <span key={n} className={"system-item " + (!ok ? "off" : "")}>
                    {ok ? <CheckCircle2 /> : <Circle />}
                    {n}
                  </span>
                ))}
              </div>
              <div className="workspace-grid">
                <div className="stack">
                  <Panel
                    title="账号"
                    number="01"
                    action={
                      <span className="subtitle">选择本次测试使用的账号</span>
                    }
                  >
                    <div className="panel-body split">
                      <div className="numbers">
                        <div className="number-block">
                          <label>已导入账号</label>
                          <strong>
                            {accounts.length}
                            <span className="hint"> 个</span>
                          </strong>
                        </div>
                        <div className="number-block">
                          <label>本次已选择</label>
                          <strong className="green">
                            {aids.length}
                            <span className="hint"> 个</span>
                          </strong>
                        </div>
                      </div>
                      <div className="toolbar">
                        <button onClick={() => openImport("accounts")}>
                          <Upload />
                          导入账号
                        </button>
                        <button
                          onClick={() =>
                            setModal({ type: "select", kind: "accounts" })
                          }
                        >
                          选择账号 <ChevronRight />
                        </button>
                      </div>
                    </div>
                  </Panel>
                  <Panel
                    title="测试数据"
                    number="02"
                    action={
                      <span className="subtitle">一个账号，对应一条数据</span>
                    }
                  >
                    <div className="panel-body">
                      <div className="split">
                        <div className="numbers">
                          <div className="number-block">
                            <label>可用测试数据</label>
                            <strong>
                              {cards.filter((c) => !c.used).length}
                              <span className="hint"> 条</span>
                            </strong>
                          </div>
                          <div className="number-block">
                            <label>本次已选择</label>
                            <strong className="green">
                              {cids.length}
                              <span className="hint"> 条</span>
                            </strong>
                          </div>
                        </div>
                        <div className="toolbar">
                          <button onClick={() => openImport("cards")}>
                            <Upload />
                            导入测试数据
                          </button>
                          <button
                            onClick={() =>
                              setModal({ type: "select", kind: "cards" })
                            }
                          >
                            选择数据
                          </button>
                        </div>
                      </div>
                      <p className="hint">
                        <ShieldCheck
                          style={{
                            width: 12,
                            verticalAlign: "middle",
                            marginRight: 5,
                          }}
                        />
                        仅使用合成测试数据，敏感字段始终遮罩显示。
                        {!binding && " 当前 Production UI 任务不使用卡片数据。"}
                      </p>
                    </div>
                  </Panel>
                  <Panel title="任务" number="03">
                    <div className="panel-body">
                      <Field
                        label="选择测试任务"
                        help="用途：确定本次运行的唯一配置 · 必填 · 从已启用任务选择；示例：Local Sandbox Binding。"
                      >
                        <select
                          value={taskId}
                          onChange={(e) => {
                            setTaskId(+e.target.value);
                            setCheck(null);
                          }}
                        >
                          {tasks.map((t) => (
                            <option
                              key={t.id}
                              value={t.id}
                              disabled={!t.enabled}
                            >
                              {t.name}
                              {!t.enabled ? "（停用）" : ""}
                            </option>
                          ))}
                        </select>
                      </Field>
                      {currentTask && (
                        <div className="task-meta">
                          <div>
                            <b>目标地址</b>{" "}
                            <span className="url">
                              {currentTask.target_url}
                            </span>
                          </div>
                          <div>
                            <b>
                              {currentTask.environment} · v{currentTask.version}
                            </b>
                            　{currentTask.description}
                          </div>
                        </div>
                      )}
                    </div>
                  </Panel>
                  <Panel title="网络" number="04">
                    <div className="panel-body">
                      <Field
                        label="连接方式"
                        help="用途：为本次运行选择网络 · 必填 · Direct 或已配置代理；示例：Direct。选择后执行准备检查。"
                      >
                        <select
                          value={networkId}
                          onChange={(e) => {
                            setNetworkId(+e.target.value);
                            setCheck(null);
                          }}
                        >
                          {networks.map((n) => (
                            <option key={n.id} value={n.id}>
                              {n.name} · {n.protocol}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>
                  </Panel>
                </div>
                <div className="stack">
                  <Panel title="准备状态" number="05">
                    <div className="panel-body">
                      {[
                        ["账号", aids.length > 0, Users],
                        [
                          "测试数据",
                          !binding ||
                            (cids.length >= aids.length && cids.length > 0),
                          CreditCard,
                        ],
                        ["任务", currentTask?.enabled, Layers],
                        ["目标地址", currentTask?.target_url, Globe],
                        ["Chromium", check?.chromium, Activity],
                        ["网络", check?.connected, Globe],
                      ].map(([name, ok, Icon]) => (
                        <div className="check-row" key={name}>
                          <span>
                            <Icon />
                            {name}
                          </span>
                          <span className={ok ? "ok" : "no"}>
                            {ok ? <CheckCircle2 /> : <Circle />}
                            {ok ? "就绪" : "待检查"}
                          </span>
                        </div>
                      ))}
                      <div className="prepare-summary">
                        <span>账号 {aids.length}</span>
                        <span>数据 {binding ? cids.length : "无需"}</span>
                        <span>
                          可执行{" "}
                          {binding
                            ? Math.min(aids.length, cids.length)
                            : aids.length}
                        </span>
                      </div>
                      {check?.reasons?.length > 0 && (
                        <ul className="check-list">
                          {check.reasons.map((r) => (
                            <li key={r}>{r}</li>
                          ))}
                        </ul>
                      )}
                      {!aids.length && <p className="hint">请先选择账号</p>}
                      {binding && aids.length > cids.length && (
                        <p className="hint">
                          测试数据不足，本次最多执行 {cids.length} 条
                        </p>
                      )}
                      <button
                        style={{ width: "100%", marginTop: 20 }}
                        disabled={checking || working}
                        onClick={() => act(doCheck)}
                      >
                        <RefreshCw />
                        {checking ? "正在验证浏览器与网络…" : "检查准备状态"}
                      </button>
                      <button
                        className="primary start"
                        disabled={!check?.ready || working || !!live}
                        onClick={() =>
                          act(async () => {
                            const result = await api("/runs", "POST", {
                              ...plan(),
                              proof: check.proof,
                            });
                            setCheck(null);
                            await openRun(result.id);
                            await refresh();
                          })
                        }
                      >
                        <Play />
                        START
                      </button>
                      <p className="start-note">
                        {live
                          ? "已有任务正在运行，请查看运行记录"
                          : "检查通过后可开始 · 真实 Chromium 执行"}
                      </p>
                    </div>
                  </Panel>
                  <div className="info-box">
                    <strong>
                      <ShieldCheck
                        style={{ verticalAlign: "middle", marginRight: 6 }}
                      />
                      每次运行，独立记录
                    </strong>
                    账号、任务版本、结果和调试证据都关联至独立
                    Run。遇到未知结果将显示 ERROR，不会默认成功。
                  </div>
                </div>
              </div>
              <Panel
                className="recent"
                title="最近运行"
                action={
                  <button
                    className="ghost"
                    onClick={() => changePage("运行记录")}
                  >
                    全部记录 <ArrowRight />
                  </button>
                }
              >
                <RunTable
                  runs={runs.slice(0, 5)}
                  open={(id) => act(() => openRun(id))}
                />
              </Panel>
            </>
          )}
          {["账号", "测试数据"].includes(page) && (
            <>
              <div className="title-row">
                <div>
                  <h1>{page}</h1>
                  <p className="subtitle">
                    {page === "账号"
                      ? "导入、整理和选择账号，Session 自动管理。"
                      : "合成支付测试数据 · 自动整理、去重和遮罩。"}
                  </p>
                </div>
                <button
                  className="primary"
                  onClick={() =>
                    openImport(page === "账号" ? "accounts" : "cards")
                  }
                >
                  <Plus />
                  粘贴导入
                </button>
              </div>
              <Panel
                title={
                  page === "账号"
                    ? `账号库 · ${accounts.length}`
                    : `测试数据 · ${cards.length}（未使用 ${cards.filter((c) => !c.used).length} / 已使用 ${cards.filter((c) => c.used).length}）`
                }
              >
                <div className="filters">
                  <Field
                    label="搜索"
                    help="可选 · 搜索邮箱或遮罩数据；示例：example.com。"
                  >
                    <input
                      placeholder="搜索邮箱 / 遮罩数据"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </Field>
                  <Field
                    label="筛选状态"
                    help="可选 · 从列表选择；示例：未使用。"
                  >
                    <select
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option value="">全部</option>
                      {(page === "账号"
                        ? ["NONE", "VALID", "EXPIRED"]
                        : ["未使用", "已使用"]
                      ).map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </Field>
                  <div className="toolbar">
                    {["TXT", "CSV"].map((ext) => (
                      <button
                        key={ext}
                        onClick={() =>
                          openImport(page === "账号" ? "accounts" : "cards")
                        }
                      >
                        <Upload />
                        {ext} 导入
                      </button>
                    ))}
                    <button
                      onClick={() =>
                        download(
                          page === "账号"
                            ? "/accounts/export"
                            : "/cards/export",
                        )
                      }
                    >
                      <Download />
                      {page === "账号" ? "导出" : "导出安全字段"}
                    </button>
                    <button
                      className="danger"
                      disabled={!(page === "账号" ? aids : cids).length}
                      onClick={() =>
                        remove(
                          page === "账号" ? "accounts" : "cards",
                          page === "账号" ? aids : cids,
                        )
                      }
                    >
                      <Trash2 />
                      删除选中
                    </button>
                    <button
                      className="danger"
                      onClick={() =>
                        remove(page === "账号" ? "accounts" : "cards", [], true)
                      }
                    >
                      清空
                    </button>
                  </div>
                </div>
                <DataTable
                  kind={page === "账号" ? "accounts" : "cards"}
                  data={filtered(page === "账号" ? accounts : cards).filter(
                    (x) =>
                      !filter ||
                      (page === "账号"
                        ? x.session === filter
                        : (filter === "已使用") === !!x.used),
                  )}
                  ids={page === "账号" ? aids : cids}
                  toggle={(id) =>
                    toggle(
                      id,
                      page === "账号" ? aids : cids,
                      page === "账号" ? setAids : setCids,
                    )
                  }
                  clear={(id) =>
                    act(async () => {
                      await api("/accounts/" + id + "/clear-session", "POST");
                      await refresh();
                    })
                  }
                  retest={(id) => {
                    setAids([id]);
                    setCheck(null);
                    changePage("首页");
                  }}
                />
              </Panel>
            </>
          )}
          {page === "任务" && (
            <>
              <div className="title-row">
                <div>
                  <h1>任务</h1>
                  <p className="subtitle">
                    明确目标地址。每次运行只使用选中任务的配置。
                  </p>
                </div>
                <button
                  className="primary"
                  onClick={() => {
                    setEditor({
                      name: "",
                      description: "",
                      environment: "QA",
                      base_url: "",
                      login_url: "",
                      target_url: "",
                      enabled: true,
                      authorized: false,
                    });
                    setModal({ type: "task" });
                  }}
                >
                  <Plus />
                  新增任务
                </button>
              </div>
              <div className="task-list">
                {tasks.map((t) => (
                  <Panel
                    key={t.id}
                    title={t.name}
                    action={
                      <div className="toolbar">
                        <Badge value={t.enabled ? "ENABLED" : "DISABLED"} />
                        <button
                          onClick={() => {
                            setEditor(t);
                            setModal({ type: "task" });
                          }}
                        >
                          修改任务
                        </button>
                      </div>
                    }
                  >
                    <div className="panel-body">
                      <div className="toolbar">
                        <Badge value={t.environment} />
                        <span className="subtitle">版本 {t.version}</span>
                      </div>
                      <p>{t.description}</p>
                      <p className="url">{t.target_url}</p>
                    </div>
                  </Panel>
                ))}
              </div>
            </>
          )}
          {page === "运行记录" && (
            <>
              <div className="title-row">
                <div>
                  <h1>{runId && run ? `Run #${runId}` : "运行记录"}</h1>
                  <p className="subtitle">
                    {runId && run
                      ? `${run.task.name} · v${run.task_version} · ${run.network} · ${time(run.started_at)}`
                      : "每次运行独立保存，结果和原因一目了然。"}
                  </p>
                </div>
                <div className="toolbar">
                  {runId ? (
                    <button
                      onClick={() => {
                        setRunId(null);
                        setRun(null);
                      }}
                    >
                      返回全部记录
                    </button>
                  ) : (
                    <button
                      className="danger"
                      disabled={!runIds.length}
                      onClick={() => remove("runs", runIds)}
                    >
                      <Trash2 />
                      删除选中 Run
                    </button>
                  )}
                </div>
              </div>
              {runId && run ? (
                <>
                  <p className="section-note url">
                    目标：{run.task.target_url}
                  </p>
                  <div className="stats">
                    {[
                      "SUCCESS",
                      "FAIL",
                      "ERROR",
                      "RUNNING",
                      "WAITING",
                      "CANCELLED",
                    ].map((s) => (
                      <div className="stat" key={s}>
                        <strong>
                          {run.results.filter((r) => r.status === s).length}
                        </strong>
                        <span>{s}</span>
                      </div>
                    ))}
                  </div>
                  <Panel
                    title={`进度 ${run.results.filter((r) => !["WAITING", "RUNNING"].includes(r.status)).length} / ${run.results.length}`}
                    action={
                      ["RUNNING", "QUEUED"].includes(run.status) ? (
                        <button
                          className="danger"
                          onClick={() =>
                            act(async () => {
                              await api(`/runs/${runId}/stop`, "POST");
                              setNotice(
                                "停止请求已发送，正在关闭浏览器并保存结果",
                              );
                            })
                          }
                        >
                          <Square />
                          STOP
                        </button>
                      ) : (
                        <Badge value={run.status} />
                      )
                    }
                  >
                    <div className="panel-body">
                      <div className="split">
                        <span>
                          {run.results.find((r) => r.status === "RUNNING")
                            ?.email || "当前没有执行中的账号"}
                        </span>
                        <Badge
                          value={
                            run.results.find((r) => r.status === "RUNNING")
                              ?.step || run.status
                          }
                        />
                      </div>
                      <div className="progress">
                        <div
                          style={{
                            width:
                              (run.results.filter(
                                (r) =>
                                  !["WAITING", "RUNNING"].includes(r.status),
                              ).length /
                                Math.max(1, run.results.length)) *
                                100 +
                              "%",
                          }}
                        />
                      </div>
                      <div className="toolbar">
                        <button
                          onClick={() =>
                            download(`/runs/${runId}/export?format=txt`)
                          }
                        >
                          <Download />
                          导出 TXT
                        </button>
                        <button
                          onClick={() =>
                            download(`/runs/${runId}/export?format=csv`)
                          }
                        >
                          <Download />
                          导出 CSV
                        </button>
                        <button
                          className="danger"
                          disabled={!resultIds.length || !!live}
                          onClick={() =>
                            act(async () => {
                              if (
                                !window.confirm(
                                  "确认删除选中结果及其调试文件？",
                                )
                              )
                                return;
                              await api(
                                `/runs/${runId}/results/delete`,
                                "POST",
                                { ids: resultIds, confirmed: true },
                              );
                              setRun(await api("/runs/" + runId));
                              setResultIds([]);
                            })
                          }
                        >
                          删除选中
                        </button>
                        <button
                          className="danger"
                          disabled={!!live}
                          onClick={() =>
                            act(async () => {
                              if (
                                !window.confirm(
                                  "确认删除本次 Run、结果及所有关联文件？账号本身会保留。",
                                )
                              )
                                return;
                              await api("/runs/delete", "POST", {
                                ids: [runId],
                                confirmed: true,
                              });
                              setRunId(null);
                              setRun(null);
                              await refresh();
                            })
                          }
                        >
                          删除本次 Run
                        </button>
                      </div>
                    </div>
                    <div className="filters">
                      <Field
                        label="搜索账号或原因"
                        help="可选 · 文本；示例：DECLINED。"
                      >
                        <input
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                          placeholder="搜索账号、结果代码"
                        />
                      </Field>
                      <Field
                        label="结果筛选"
                        help="可选 · 从列表选择；示例：ERROR。"
                      >
                        <select
                          value={filter}
                          onChange={(e) => setFilter(e.target.value)}
                        >
                          <option value="">全部结果</option>
                          {["SUCCESS", "FAIL", "ERROR", "CANCELLED"].map(
                            (s) => (
                              <option key={s}>{s}</option>
                            ),
                          )}
                        </select>
                      </Field>
                    </div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>选择</th>
                            <th>账号</th>
                            <th>数据</th>
                            <th>结果</th>
                            <th>原因 / 当前步骤</th>
                            <th>耗时</th>
                            <th>调试证据</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filtered(run.results)
                            .filter((r) => !filter || r.status === filter)
                            .map((r) => (
                              <tr key={r.id}>
                                <td>
                                  <input
                                    type="checkbox"
                                    aria-label={`选择结果 ${r.id}`}
                                    checked={resultIds.includes(r.id)}
                                    onChange={() =>
                                      toggle(r.id, resultIds, setResultIds)
                                    }
                                  />
                                </td>
                                <td>{r.email}</td>
                                <td>{r.masked}</td>
                                <td>
                                  <Badge value={r.status} />
                                </td>
                                <td>{r.code || r.step}</td>
                                <td>{r.duration.toFixed(1)}s</td>
                                <td>
                                  <div className="toolbar">
                                    {r.artifacts.map((name) => (
                                      <button
                                        key={name}
                                        onClick={() =>
                                          act(async () => {
                                            const url = `/runs/${runId}/results/${r.id}/artifacts/${name}`;
                                            if (name === "trace.zip")
                                              download(url);
                                            else if (name === "screenshot.png")
                                              setModal({
                                                type: "image",
                                                url: "/api" + url,
                                              });
                                            else {
                                              const response = await fetch(
                                                "/api" + url,
                                              );
                                              if (!response.ok)
                                                throw new Error("日志不可用");
                                              setLogs(await response.text());
                                              setModal({ type: "logs" });
                                            }
                                          })
                                        }
                                      >
                                        {name === "trace.zip"
                                          ? "下载 Trace"
                                          : name === "screenshot.png"
                                            ? "查看截图"
                                            : "查看日志"}
                                      </button>
                                    ))}
                                  </div>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </Panel>
                  <Panel className="recent" title="实时日志">
                    <pre className="log">
                      {liveLogs
                        .map(
                          (e) =>
                            `${e.time.slice(11, 19)}  ${e.account}  ${e.step}  ${e.action}`,
                        )
                        .join("\n") || "等待运行日志…"}
                    </pre>
                  </Panel>
                </>
              ) : (
                <Panel title={`全部运行 · ${runs.length}`}>
                  <div className="filters">
                    <Field
                      label="搜索任务或 Run"
                      help="可选 · 文本；示例：Sandbox。"
                    >
                      <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="搜索任务或 Run ID"
                      />
                    </Field>
                    <Field
                      label="日期筛选"
                      help="可选 · 选择日期；示例：2026-09-27。"
                    >
                      <input
                        type="date"
                        value={date}
                        onChange={(e) => setDate(e.target.value)}
                      />
                    </Field>
                  </div>
                  <RunTable
                    runs={filtered(runs).filter(
                      (r) => !date || r.started_at.startsWith(date),
                    )}
                    open={(id) => act(() => openRun(id))}
                    ids={runIds}
                    toggle={(id) => toggle(id, runIds, setRunIds)}
                  />
                </Panel>
              )}
            </>
          )}
          {page === "设置" && (
            <>
              <div className="title-row">
                <div>
                  <h1>设置</h1>
                  <p className="subtitle">
                    管理网络与数据，不需要通过终端清理。
                  </p>
                </div>
                <button onClick={() => act(refresh)}>
                  <RefreshCw />
                  刷新
                </button>
              </div>
              <div className="stack">
                <Panel title="数据管理">
                  <div className="panel-body">
                    <div className="summary-grid">
                      {[
                        ["accounts", "账号"],
                        ["cards", "测试数据"],
                        ["runs", "Runs"],
                        ["results", "Results"],
                        ["sessions", "Sessions"],
                        ["disk_bytes", "磁盘占用"],
                        ["screenshots", "Screenshots"],
                        ["traces", "Traces"],
                        ["logs", "Logs"],
                      ].map(([key, title]) => (
                        <div className="stat" key={key}>
                          <strong style={{ fontSize: 21 }}>
                            {[
                              "disk_bytes",
                              "screenshots",
                              "traces",
                              "logs",
                            ].includes(key)
                              ? bytes(stats[key] || 0)
                              : stats[key] || 0}
                          </strong>
                          <span>{title}</span>
                        </div>
                      ))}
                    </div>
                    <div className="toolbar" style={{ margin: "22px 0" }}>
                      <button onClick={() => changePage("账号")}>
                        管理账号
                      </button>
                      <button onClick={() => changePage("测试数据")}>
                        管理测试数据
                      </button>
                      <button
                        onClick={() => {
                          setRunId(null);
                          changePage("运行记录");
                        }}
                      >
                        管理 Runs
                      </button>
                    </div>
                    <Field
                      label="历史清理范围"
                      help="用途：按 Run 开始时间清理 · 必填 · 选择 7 天以前、30 天以前或全部；示例：30 天以前。"
                    >
                      <select
                        value={days}
                        onChange={(e) => setDays(+e.target.value)}
                      >
                        <option value={7}>7 天以前</option>
                        <option value={30}>30 天以前</option>
                        <option value={0}>全部</option>
                      </select>
                    </Field>
                    <div className="toolbar">
                      {[
                        ["runs", "清理历史 Run"],
                        ["screenshots", "清理 Screenshots"],
                        ["traces", "清理 Trace"],
                        ["logs", "清理 Logs"],
                        ["sessions", "清理失效 Session"],
                      ].map(([kind, label]) => (
                        <button
                          className="danger"
                          key={kind}
                          disabled={!!live}
                          onClick={() =>
                            act(async () => {
                              if (
                                !window.confirm(
                                  `确认${label}？此操作无法撤销。`,
                                )
                              )
                                return;
                              setStats(
                                await api("/data-management/cleanup", "POST", {
                                  kind,
                                  days,
                                  confirmed: true,
                                }),
                              );
                              await refresh();
                              setNotice("清理完成");
                            })
                          }
                        >
                          <Trash2 />
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                </Panel>
                <Panel
                  title="网络配置"
                  action={
                    <button
                      onClick={() => {
                        setEditor({
                          name: "",
                          protocol: "HTTP",
                          host: "",
                          port: 8080,
                          username: "",
                          password: "",
                        });
                        setModal({ type: "network" });
                      }}
                    >
                      <Plus />
                      添加网络
                    </button>
                  }
                >
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>名称</th>
                          <th>协议</th>
                          <th>地址</th>
                          <th>操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {networks.map((n) => (
                          <tr key={n.id}>
                            <td>{n.name}</td>
                            <td>{n.protocol}</td>
                            <td>
                              {n.host
                                ? `${n.host}:${n.port}`
                                : "直接连接目标站点"}
                            </td>
                            <td>
                              <button
                                disabled={working}
                                onClick={() =>
                                  act(async () => {
                                    const result = await api(
                                      "/preflight",
                                      "POST",
                                      { ...plan(), network_id: n.id },
                                    );
                                    setNotice(
                                      result.connected
                                        ? `Connected · Latency ${result.latency_ms} ms · ${currentTask?.target_url}`
                                        : result.reason,
                                    );
                                  })
                                }
                              >
                                <Globe />
                                测试连接
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Panel>
              </div>
            </>
          )}
          <div className="footer">
            <span>Payment Test Runner · 为清晰、可靠的测试而构建</span>
            <span>
              <span className="dot" />
              真实 Chromium · LIVE
            </span>
          </div>
        </main>
      </div>
      {modal?.type === "import" && (
        <Modal
          error={error}
          notice={notice}
          title={modal.kind === "accounts" ? "导入账号" : "导入测试数据"}
          description="先预览格式与重复项，确认后才写入数据库。错误行的原始文本保留在本地输入框中。"
          onClose={close}
        >
          <Field
            label="粘贴文本"
            help={
              modal.kind === "accounts"
                ? "用途：批量导入账号 · 必填 · 每行 email|password 或 email----password；CSV 两列 email,password。示例：demo@example.com|sandbox-pass。"
                : "用途：导入合成卡 · 必填 · 每行 number|month|year|cvc，CSV 同样四列。示例：4242424242424242|12|2035|123。支持结尾 4242 / 0002 / 3220 / 0069 / 9995 的文档测试卡。"
            }
          >
            <textarea
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setPreview(null);
              }}
              placeholder={
                modal.kind === "accounts"
                  ? "demo@example.com|sandbox-pass"
                  : "4242424242424242|12|2035|123"
              }
            />
          </Field>
          <div className="toolbar">
            {["TXT", "CSV"].map((ext) => (
              <label className="file-button" key={ext}>
                <Upload />
                &nbsp;{ext} 导入
                <input
                  type="file"
                  accept={ext === "TXT" ? ".txt" : ".csv"}
                  aria-label={`${ext} 文件导入（可选，选择对应格式文件）`}
                  onChange={(e) =>
                    act(async () => {
                      const file = e.target.files?.[0];
                      if (file) {
                        if (file.size > 2000000)
                          throw new Error("文件超过 2 MB");
                        setText(await file.text());
                        setPreview(null);
                      }
                    })
                  }
                />
              </label>
            ))}
            <button
              disabled={!text.trim() || working}
              onClick={() =>
                act(async () =>
                  setPreview(
                    await api("/import/preview", "POST", {
                      kind: modal.kind,
                      text,
                    }),
                  ),
                )
              }
            >
              预览导入
            </button>
          </div>
          {preview && (
            <>
              <div
                className="stats"
                style={{ gridTemplateColumns: "repeat(4,1fr)", marginTop: 20 }}
              >
                {[
                  ["总数", preview.total],
                  ["有效", preview.valid],
                  ["重复", preview.duplicates],
                  ["错误", preview.errors.length],
                ].map(([t, n]) => (
                  <div className="stat" key={t}>
                    <strong>{n}</strong>
                    <span>{t}</span>
                  </div>
                ))}
              </div>
              {preview.errors.map((e) => (
                <div className="error-banner" key={e.line}>
                  第 {e.line} 行 · {e.reason}
                  <br />
                  {e.raw}
                </div>
              ))}
            </>
          )}
          <div className="modal-footer">
            <button onClick={close}>取消</button>
            <button
              className="primary"
              disabled={!preview?.valid || working}
              onClick={() =>
                act(async () => {
                  const result = await api("/import/confirm", "POST", {
                    preview_id: preview.preview_id,
                  });
                  setNotice(`成功导入 ${result.imported} 条，重复数据已跳过`);
                  close();
                  setText("");
                  await refresh();
                })
              }
            >
              确认导入
            </button>
          </div>
        </Modal>
      )}
      {modal?.type === "select" && (
        <Modal
          error={error}
          notice={notice}
          title={modal.kind === "accounts" ? "选择账号" : "选择测试数据"}
          description="本次按选择顺序一对一配对。每条数据在同一个 Run 内只使用一次。"
          onClose={close}
        >
          <div className="toolbar" style={{ marginBottom: 15 }}>
            <button
              onClick={() => {
                modal.kind === "accounts"
                  ? setAids(accounts.map((x) => x.id))
                  : setCids(cards.filter((x) => !x.used).map((x) => x.id));
                setCheck(null);
              }}
            >
              全选可用
            </button>
            <button
              onClick={() => {
                modal.kind === "accounts" ? setAids([]) : setCids([]);
                setCheck(null);
              }}
            >
              取消选择
            </button>
          </div>
          <DataTable
            kind={modal.kind}
            data={
              modal.kind === "accounts"
                ? accounts
                : cards.filter((c) => !c.used)
            }
            ids={modal.kind === "accounts" ? aids : cids}
            toggle={(id) =>
              toggle(
                id,
                modal.kind === "accounts" ? aids : cids,
                modal.kind === "accounts" ? setAids : setCids,
              )
            }
          />
          <div className="modal-footer">
            <button className="primary" onClick={close}>
              确认选择
            </button>
          </div>
        </Modal>
      )}
      {modal?.type === "task" && (
        <Modal
          error={error}
          notice={notice}
          title={editor.id ? "修改任务" : "新增任务"}
          description="URL 必须完整并属于同一站点。保存修改会生成新的任务版本；旧 Run 保留原配置。"
          onClose={close}
        >
          {fields(
            "任务名称",
            "用途：区分任务 · 必填 · 1–100 字；示例：QA Payment Test。",
            "name",
          )}
          {fields(
            "任务说明",
            "用途：描述测试目标 · 可选 · 最多 500 字；示例：验证支付卡绑定结果。",
            "description",
          )}
          <div className="two-col">
            <Field
              label="环境类型"
              help="用途：确定允许的操作 · 必填 · Production 仅验证 UI；其他类型需确认授权。示例：QA。"
            >
              <select
                value={editor.environment}
                onChange={(e) =>
                  setEditor({ ...editor, environment: e.target.value })
                }
              >
                {["Production", "Sandbox", "QA", "Staging", "Internal"].map(
                  (x) => (
                    <option key={x}>{x}</option>
                  ),
                )}
              </select>
            </Field>
            <Field
              label="状态"
              help="用途：决定任务是否可运行 · 必填 · 启用或停用；示例：启用。"
            >
              <select
                value={String(editor.enabled === true || editor.enabled === 1)}
                onChange={(e) =>
                  setEditor({ ...editor, enabled: e.target.value === "true" })
                }
              >
                <option value="true">启用</option>
                <option value="false">停用</option>
              </select>
            </Field>
          </div>
          {fields(
            "Base URL",
            "用途：站点根地址 · 必填 · 完整 HTTP(S) URL，无查询参数；示例：http://127.0.0.1:8080。",
            "base_url",
          )}
          {fields(
            "Login URL",
            "用途：记录站点登录入口，正常运行先访问 Target 并等待登录跳转 · 必填 · 完整 URL；示例：http://127.0.0.1:8080/login。",
            "login_url",
          )}
          {fields(
            "Target URL",
            "用途：登录后进入的支付测试页面 · 必填 · 完整 URL；示例：http://127.0.0.1:8080/settings/payments。",
            "target_url",
          )}
          {editor.environment !== "Production" && (
            <>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={!!editor.authorized}
                  onChange={(e) =>
                    setEditor({ ...editor, authorized: e.target.checked })
                  }
                />
                我已获得该测试环境的明确授权（运行完整绑卡测试必选）
              </label>
              <div className="info-box">
                自定义测试站点需支持本工具内置页面适配协议。特殊站点需添加内部
                Task 适配器，详见 README；未识别的页面会返回明确错误。
              </div>
            </>
          )}
          <div className="modal-footer">
            <button
              disabled={working}
              onClick={() =>
                act(async () => {
                  const r = await api(
                    "/tasks/test-address?network_id=" + networkId,
                    "POST",
                    editor,
                  );
                  setNotice(
                    r.connected ? `Connected · ${r.latency_ms} ms` : r.reason,
                  );
                })
              }
            >
              测试地址
            </button>
            <button
              disabled={working}
              className="primary"
              onClick={() =>
                act(async () => {
                  await api(
                    "/tasks" + (editor.id ? "/" + editor.id : ""),
                    editor.id ? "PUT" : "POST",
                    editor,
                  );
                  setCheck(null);
                  close();
                  await refresh();
                })
              }
            >
              保存
            </button>
          </div>
        </Modal>
      )}
      {modal?.type === "network" && (
        <Modal
          error={error}
          notice={notice}
          title="添加网络"
          description="用于连接本次任务目标。网络错误不会触发 IP 轮换。"
          onClose={close}
        >
          {fields(
            "名称",
            "用途：区分连接配置 · 必填 · 文本；示例：QA HTTP Proxy。",
            "name",
          )}
          <Field
            label="协议"
            help="用途：选择代理协议 · 必填 · HTTP 或 SOCKS5；示例：HTTP。"
          >
            <select
              value={editor.protocol}
              onChange={(e) =>
                setEditor({ ...editor, protocol: e.target.value })
              }
            >
              <option>HTTP</option>
              <option>SOCKS5</option>
            </select>
          </Field>
          {fields(
            "Host",
            "用途：代理服务器地址 · 必填 · IP 或域名，不含协议及端口；示例：192.0.2.10。",
            "host",
          )}
          {fields(
            "Port",
            "用途：代理服务器端口 · 必填 · 1–65535 整数；示例：8080。",
            "port",
            "number",
          )}
          {fields(
            "Username",
            "用途：HTTP 代理认证用户名 · 可选 · 文本；示例：qa-user。SOCKS5 仅支持无认证。",
            "username",
          )}
          {fields(
            "Password",
            "用途：HTTP 代理认证密码 · 可选 · 文本；示例：由代理管理员提供的密码。加密保存。",
            "password",
            "password",
          )}
          <div className="modal-footer">
            <button
              className="primary"
              disabled={working}
              onClick={() =>
                act(async () => {
                  await api("/networks", "POST", {
                    ...editor,
                    port: +editor.port,
                  });
                  close();
                  await refresh();
                })
              }
            >
              保存网络
            </button>
          </div>
        </Modal>
      )}
      {modal?.type === "logs" && (
        <Modal
          error={error}
          notice={notice}
          title="运行日志"
          description="记录步骤、动作和结果；敏感字段不会写入日志。"
          onClose={close}
        >
          <pre className="log">{logs}</pre>
        </Modal>
      )}
      {modal?.type === "image" && (
        <Modal
          error={error}
          notice={notice}
          title="真实浏览器截图"
          description="输入框和 iframe 已遮罩。"
          onClose={close}
        >
          <img
            className="screen-image"
            src={modal.url}
            alt="当前结果的真实 Chromium 截图"
          />
        </Modal>
      )}
    </>
  );
}

function DataTable({ kind, data, ids, toggle, clear, retest }) {
  if (!data.length) return <Empty text="暂无数据，导入后即可在这里管理。" />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>选择</th>
            <th>{kind === "accounts" ? "Email" : "遮罩测试数据"}</th>
            <th>状态</th>
            {kind === "accounts" && (
              <>
                <th>Session</th>
                <th>上次结果</th>
              </>
            )}
            <th>创建时间</th>
            {clear && <th>操作</th>}
          </tr>
        </thead>
        <tbody>
          {data.map((x) => (
            <tr key={x.id}>
              <td>
                <input
                  type="checkbox"
                  aria-label={`选择 ${x.email || x.masked}`}
                  checked={ids.includes(x.id)}
                  onChange={() => toggle(x.id)}
                />
              </td>
              <td>{x.email || x.masked}</td>
              <td>
                <Badge
                  value={
                    kind === "accounts"
                      ? x.status
                      : x.used
                        ? "已使用"
                        : "未使用"
                  }
                />
              </td>
              {kind === "accounts" && (
                <>
                  <td>
                    <Badge value={x.session} />
                  </td>
                  <td>{x.last_result || "—"}</td>
                </>
              )}
              <td>{time(x.created_at)}</td>
              {clear && (
                <td>
                  <div className="toolbar">
                    <button onClick={() => clear(x.id)}>清除 Session</button>
                    <button
                      onClick={() => {
                        clear(x.id);
                        retest(x.id);
                      }}
                    >
                      重新登录
                    </button>
                    <button onClick={() => retest(x.id)}>重新测试</button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function RunTable({ runs, open, ids, toggle }) {
  if (!runs.length)
    return (
      <Empty text="还没有运行记录。准备好账号和任务，开始第一次测试吧。" />
    );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {ids && <th>选择</th>}
            <th>Run ID</th>
            <th>任务</th>
            <th>数量</th>
            <th>SUCCESS</th>
            <th>FAIL</th>
            <th>ERROR</th>
            <th>状态</th>
            <th>开始时间</th>
            <th>耗时</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              {ids && (
                <td>
                  <input
                    type="checkbox"
                    aria-label={`选择 Run ${r.id}`}
                    checked={ids.includes(r.id)}
                    onChange={() => toggle(r.id)}
                  />
                </td>
              )}
              <td>#{String(r.id).padStart(3, "0")}</td>
              <td>{r.task}</td>
              <td>{r.total}</td>
              <td style={{ color: "var(--green)" }}>{r.counts.SUCCESS || 0}</td>
              <td>{r.counts.FAIL || 0}</td>
              <td>{r.counts.ERROR || 0}</td>
              <td>
                <Badge value={r.status} />
              </td>
              <td>{time(r.started_at)}</td>
              <td>
                {r.ended_at
                  ? (
                      (new Date(r.ended_at) - new Date(r.started_at)) /
                      1000
                    ).toFixed(1) + "s"
                  : "—"}
              </td>
              <td>
                <button className="ghost" onClick={() => open(r.id)}>
                  查看 <ChevronRight />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

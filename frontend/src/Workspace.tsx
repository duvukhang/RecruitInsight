import { Button } from "./components/ui/button";
import ConfigPanel from "./ConfigPanel";
import { QualityRecords, Benchmarks, ModelDiagnostics } from "./ExtraReports";
import React, { createContext, useContext, useState } from "react";
import { Routes, Route, Link, useLocation, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Database,
  Building2,
  Coins,
  BriefcaseBusiness,
  Upload,
  Play,
  RefreshCw,
  ArrowRight,
  LoaderCircle,
  CheckCircle2,
  Filter,
} from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "./api";
import { Chart } from "./Chart";
import AdminUsers, { AuditLogs } from './AdminUsers';
import Sources from './Sources';
import QualityDashboard from './QualityDashboard';
import Profile from './Profile';
import { can, routePermission, Forbidden, PermissionGate } from './permissions';
import { StatCard, InsightPanel, PageHeader, FilterToolbar, DetailDialog, ModelBadge } from './components/insights';
type Row = Record<string, any>;
const Context = createContext({
  version: "",
  province: "",
  industry: "",
  postedFrom: "",
  postedTo: "",
  role: "VIEWER",
});
function useData(path: string, filtered = false, poll = false) {
  const filter = useContext(Context);
  const params = new URLSearchParams();
  if (filter.version && !/[?&]dataset_version=/.test(path))
    params.set("dataset_version", filter.version);
  if (filtered && filter.province) params.set("province", filter.province);
  if (filtered && filter.industry) params.set("industry", filter.industry);
  if (filtered && filter.postedFrom)
    params.set("posted_from", filter.postedFrom);
  if (filtered && filter.postedTo) params.set("posted_to", filter.postedTo);
  const url = path + (path.includes("?") ? "&" : "?") + params;
  return useQuery({
    queryKey: [url],
    queryFn: () => api(url),
    refetchInterval: poll ? 4000 : path.startsWith("/analytics") ? 8000 : false,
  });
}
function Status({
  query,
  children,
}: {
  query: any;
  children: React.ReactNode;
}) {
  if (query.isPending)
    return (
      <div className="empty">
        <LoaderCircle className="spin" size={20} /> Đang tải dữ liệu…
      </div>
    );
  if (query.error)
    return (
      <div className="error" role="alert">
        {query.error.message} <Link to="/datasets">Quản lý dữ liệu</Link>{" "}
        <button onClick={() => query.refetch()}>Thử lại</button>
      </div>
    );
  return <>{children}</>;
}
const Panel = InsightPanel;
export function money(value: number | null | undefined) {
  return value == null
    ? "Chưa có dữ liệu"
    : new Intl.NumberFormat("vi-VN").format(Math.round(value)) + " ₫";
}
function ShortId({ id }: { id: string }) {
  return (
    <span title={id} className="mono">
      {id?.slice(0, 8)}
    </span>
  );
}
function Badge({ status }: { status: string }) {
  return (
    <span
      className={
        "badge " +
        (["PUBLISHED", "COMPLETED", "ACTIVE"].includes(status)
          ? "green"
          : ["FAILED", "CANCELLED"].includes(status)
            ? "red"
            : "")
      }
    >
      {status}
    </span>
  );
}
function Table({
  columns,
  rows,
}: {
  columns: { name: string; render: (row: Row) => React.ReactNode }[];
  rows: Row[];
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.name}>{c.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r._id || i}>
              {columns.map((c) => (
                <td key={c.name}>{c.render(r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <div className="empty">Chưa có dữ liệu phù hợp.</div>}
    </div>
  );
}
function Dashboard() {
  const { role } = useContext(Context);
  const overview = useData("/analytics/overview", true),
    trends = useData("/analytics/job-trends", true),
    industry = useData("/analytics/salary-by-industry", true),
    skills = useData("/analytics/top-skills", true);
  const years = useData('/analytics/job-years', true);
  const locations = useData('/analytics/salary-by-location', true), histogram = useData('/analytics/salary-distribution', true);
  const data = overview.data?.data;
  const meta = overview.data?.meta;
  const activeModel = useQuery({ queryKey: ['dashboard-active-model', role], queryFn: () => api('/models?active_only=true'), enabled: can(role, 'predict'), refetchInterval: 8000 });
  const latestETL = useQuery({ queryKey: ['dashboard-latest-etl', meta?.dataset_version, role],
    queryFn: () => api('/etl/jobs?page_size=1&job_type=ETL&dataset_version=' + encodeURIComponent(meta?.dataset_version)),
    enabled: can(role, 'manage') && !!meta?.dataset_version, refetchInterval: 8000 });
  const model = activeModel.data?.data?.[0], lastJob = latestETL.data?.data?.[0];
  return (
    <Status query={overview}>
      {data && (
        <div className="dashboard-v3">
          <section className="dashboard-hero">
            <div className="hero-copy"><div className="hero-kicker"><span className="live-dot" /> TỔNG QUAN TUYỂN DỤNG</div><h2>Dữ liệu tuyển dụng.<br /><span>Góc nhìn rộng hơn.</span></h2>
              <div className="hero-actions"><Link className="hero-primary" to="/jobs"><BriefcaseBusiness size={17} /> Khám phá việc làm <ArrowRight size={16} /></Link><Link className="hero-secondary" to="/profile">Hồ sơ của tôi ↗</Link></div>
            </div>
            <div className="hero-observatory"><div className="data-orbit" aria-hidden="true"><i /><i /><i /><Database size={44} /></div><div className="hero-count"><span>TIN TRONG PHẠM VI ĐANG XEM</span><strong>{data.total_jobs?.toLocaleString('vi-VN')}</strong><small>{data.total_industries ?? '—'} ngành có thông tin · {data.total_provinces ?? '—'} địa phương</small></div></div>
          </section>
          <div className="stat-grid four">
            {[
              {
                label: "Tổng tin tuyển dụng",
                value: data.total_jobs?.toLocaleString("vi-VN"),
                icon: BriefcaseBusiness,
              },
              {
                label: "Doanh nghiệp",
                value: data.total_companies,
                icon: Building2,
              },
              {
                label: "Lương trung vị / tháng",
                value: money(data.median_salary_vnd),
                icon: Coins,
                note: `${data.salary_sample_size} tin đủ nhãn lương`,
              },
              {
                label: "Tin có nhãn lương",
                value: data.total_jobs
                  ? Math.round(
                      (100 * data.salary_sample_size) / data.total_jobs,
                    ) + "%"
                  : "—",
                icon: Database,
              },
            ].map((s) => (
              <StatCard key={s.label} {...s} />
            ))}
          </div>
          <div className="dashboard-summary">
            {can(role, 'predict') && <Panel title="Mô hình đang dùng · toàn hệ thống"><Status query={activeModel}>
              {model ? <div className="summary-body"><ModelBadge active /><h3>{model.algorithm}</h3><div>MAE: {money(model.test_metrics?.mae)} · RMSE: {money(model.test_metrics?.rmse)}</div><div>N train/validation/test: {model.sample_counts?.train ?? '—'} / {model.sample_counts?.validation ?? '—'} / {model.sample_counts?.test ?? '—'}</div><div className="data-foot">Dataset huấn luyện: <ShortId id={model.dataset_version} /> · Model: <ShortId id={model._id} /></div><Link to="/models">Xem registry & đánh giá</Link></div> : <div className="empty">Chưa có mô hình được kích hoạt.</div>}
            </Status></Panel>}
            {can(role, 'manage') && <Panel title="ETL gần nhất · phiên bản đang xem"><Status query={latestETL}>
              {lastJob ? <div className="summary-body"><Badge status={lastJob.status} /><div className="data-foot">Job: <ShortId id={lastJob._id} /> · {new Date(lastJob.created_at).toLocaleString('vi-VN')}</div><div>{lastJob.metrics?.counts ? `${lastJob.metrics.counts.raw} raw · ${lastJob.metrics.counts.clean} clean · ${lastJob.metrics.counts.invalid} invalid · ${lastJob.metrics.counts.duplicate} duplicate` : lastJob.error?.message || 'Đang chờ kết quả xử lý.'}</div><Link to="/etl">Xem giám sát ETL</Link></div> : <div className="empty">Chưa có ETL run cho phiên bản này.</div>}
            </Status></Panel>}
          </div>
          <div className="chart-grid">
            <Panel
              title={trends.data?.data?.length ? 'Số tin theo tháng đăng tuyển' : 'Số tin theo năm quan sát'}
            >
              <Status query={trends}>
                <Chart
                  labels={(trends.data?.data?.length ? trends.data.data : years.data?.data || []).map((r: Row) => r.month || String(r.posted_year))}
                  values={(trends.data?.data?.length ? trends.data.data : years.data?.data || []).map((r: Row) => r.count)}
                  type="line"
                />
              </Status>
            </Panel>
            <Panel
              title="Ngành nào xuất hiện nhiều tin nhất?"
            >
              <Status query={industry}>
                <Chart
                  labels={(industry.data?.data || []).map(
                    (r: Row) => r.industry,
                  )}
                  values={(industry.data?.data || []).map((r: Row) => r.jobs)}
                  color="#73a6b7"
                />
              </Status>
            </Panel>
          </div>
          <Panel
            title="Kỹ năng được yêu cầu"
          >
            <Status query={skills}>
              <Chart
                labels={(skills.data?.data || [])
                  .slice(0, 12)
                  .map((r: Row) => r.skill)}
                values={(skills.data?.data || [])
                  .slice(0, 12)
                  .map((r: Row) => r.count)}
              />
            </Status>
          </Panel>
          <div className="chart-grid extra-insights">
            <Panel title="Địa phương trong tập quan sát"><Status query={locations}><Chart labels={(locations.data?.data || []).slice(0, 10).map((r: Row) => r.province)} values={(locations.data?.data || []).slice(0, 10).map((r: Row) => r.jobs)} color="#46c9ad" /></Status></Panel>
            <Panel title="Phân bố lương công bố" subtitle={`Khoảng 5 triệu VND/tháng · N = ${data.salary_sample_size ?? 0} nhãn hợp lệ`}><Status query={histogram}><Chart labels={(histogram.data?.data || []).map((r: Row) => `${r.lower_vnd / 1e6}–${r.lower_vnd / 1e6 + 5}`)} values={(histogram.data?.data || []).map((r: Row) => r.count)} color="#ae93ff" /></Status></Panel>
          </div>
          <div className="panel-links">
            <Link to="/analytics/recruitment">Phân tích tin tuyển dụng</Link>
            <Link to="/analytics/salary">Khảo sát mức lương</Link>
            {can(role, 'predict') && <><Link to="/models">Đánh giá mô hình</Link><Link to="/predictions">Dự đoán mức lương</Link></>}
          </div>
        </div>
      )}
    </Status>
  );
}
function Analysis({ salary = false }: { salary?: boolean }) {
  const a = useData(
    salary ? "/analytics/salary-distribution" : "/analytics/salary-by-location",
    true,
  );
  const b = useData(
    salary ? "/analytics/salary-by-industry" : "/analytics/experience",
    true,
  );
  const overview = useData("/analytics/overview", true);
  return (
    <>
      <div className="chart-grid">
        <Panel
          title={salary ? "Lương công bố phân bố ra sao?" : "Địa phương nào có nhiều tin?"}
          subtitle={
            salary
              ? "Khoảng lương 5 triệu VND/tháng"
              : "Số lượng tin tuyển dụng"
          }
        >
          <Status query={a}>
            <Chart
              labels={(a.data?.data || []).map((r: Row) =>
                salary
                  ? `${r.lower_vnd / 1000000}–${r.lower_vnd / 1000000 + 5}tr`
                  : r.province,
              )}
              values={(a.data?.data || []).map((r: Row) =>
                salary ? r.count : r.jobs,
              )}
            />
          </Status>
        </Panel>
        <Panel
          title={salary ? "Lương trung vị khác nhau thế nào giữa các ngành?" : "Tin tuyển dụng phân bố theo kinh nghiệm thế nào?"}
          subtitle={
            salary
              ? "Trung vị · triệu VND/tháng; biểu đồ chỉ hiện nhóm từ 30 nhãn lương"
              : "Theo số năm khai báo; thiếu kinh nghiệm được giữ riêng"
          }
        >
          <Status query={b}>
            {salary && b.data?.data?.length > 0 && b.data.data.every((r: Row) => r.salary_sample_size < 30) ? <div className="empty">Chưa có ngành đủ 30 nhãn lương để vẽ biểu đồ so sánh. Xem cỡ mẫu và trung vị mô tả trong bảng.</div> : <Chart
              labels={(b.data?.data || []).map((r: Row) =>
                salary ? r.industry : r.experience_years == null ? "Chưa rõ" : String(r.experience_years),
              )}
              values={(b.data?.data || []).map((r: Row) =>
                salary
                  ? r.median_salary_vnd == null || r.salary_sample_size < 30
                    ? null
                    : r.median_salary_vnd / 1000000
                  : r.jobs,
              )}
              color="#73a6b7"
            />}
          </Status>
        </Panel>
      </div>
      {salary && (
        <Panel
          title="Các phân vị lương"
        >
          <Status query={overview}>
            <div className="percentiles">
              {["p25", "median_salary_vnd", "p75", "p90"].map((p, i) => (
                <div key={p}>
                  <span>{["P25", "Trung vị", "P75", "P90"][i]}</span>
                  <strong>{money(overview.data?.data[p])}</strong>
                </div>
              ))}
            </div>
          </Status>
        </Panel>
      )}
      <Panel title={salary ? "So sánh lương công bố theo ngành" : "Kinh nghiệm liên hệ với lương công bố thế nào?"}>
        <Status query={b}>
          <Table
            rows={b.data?.data || []}
            columns={[
              {
                name: salary ? "Ngành" : "Kinh nghiệm",
                render: (r) =>
                  salary ? r.industry : r.experience_years == null ? "Chưa rõ" : r.experience_years + " năm",
              },
              { name: "Số tin", render: (r) => r.jobs },
              { name: "Mẫu lương", render: (r) => r.salary_sample_size },
              {
                name: "Lương trung bình",
                render: (r) => money(r.mean_salary_vnd),
              },
              { name: "Trung vị", render: (r) => money(r.median_salary_vnd) },
              { name: "P25 / P75", render: (r) => `${money(r.p25)} / ${money(r.p75)}` },
              { name: "Diễn giải", render: (r) => r.salary_sample_size < 30 ? "Ít mẫu lương (<30)" : "Mô tả mẫu quan sát" },
            ]}
          />
        </Status>
      </Panel>
    </>
  );
}
function JobList() {
  const [q, setQ] = useState(""),
    [search, setSearch] = useState(""),
    [detail, setDetail] = useState<Row | null>(null);
  const [jobFilters, setJobFilters] = useState<Record<string, string>>({});
  const scope = useContext(Context);
  const signature = JSON.stringify([scope.version, scope.province, scope.industry, scope.postedFrom, scope.postedTo, search, jobFilters]);
  const [paging, setPaging] = useState({ signature: '', page: 1, cursors: [''] });
  const page = paging.signature === signature ? paging.page : 1;
  const cursors = paging.signature === signature ? paging.cursors : [''];
  function setPage(value: number) { setPaging({ signature, page: value, cursors }); }
  const extra = new URLSearchParams(Object.fromEntries(Object.entries(jobFilters).filter(([, v]) => v)));
  const query = useData(
    "/jobs?cursor=" + encodeURIComponent(cursors[page - 1] || '') + "&q=" + encodeURIComponent(search) + '&' + extra,
    true,
  );
  return (
    <>
      <form
        className="search-row"
        onSubmit={(e) => {
          e.preventDefault();
          setSearch(q);
          setPage(1);
        }}
      >
        <input
          aria-label="Tìm vị trí tuyển dụng"
          placeholder="Tìm theo vị trí hoặc doanh nghiệp…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Button>Tìm kiếm</Button>
      </form>
      <div className="admin-toolbar job-filters">
        {([['salary_min', 'Lương từ (VND/tháng)'], ['salary_max', 'Lương đến (VND/tháng)'], ['experience_min', 'Kinh nghiệm từ (năm)'], ['experience_max', 'Kinh nghiệm đến (năm)'], ['posted_year', 'Năm đăng']] as const).map(([key, label]) => <label key={key}>{label}<input type="number" min={key === 'posted_year' ? 1900 : 0} max={key.startsWith('experience') ? 60 : key === 'posted_year' ? 2099 : 1e12} value={jobFilters[key] || ''} onChange={e => { setJobFilters({ ...jobFilters, [key]: e.target.value }); setPage(1); }} /></label>)}
        <label>Loại hình<input value={jobFilters.employment_type || ''} onChange={e => { setJobFilters({ ...jobFilters, employment_type: e.target.value }); setPage(1); }} placeholder="Đúng giá trị trong nguồn" /></label>
        <label>Sắp xếp<select value={jobFilters.sort || 'posted_at'} onChange={e => { setJobFilters({ ...jobFilters, sort: e.target.value }); setPage(1); }}><option value="posted_at">Ngày đăng</option><option value="salary_mid_vnd">Lương</option><option value="experience_years">Kinh nghiệm</option><option value="job_title">Chức danh</option></select></label>
        <label>Thứ tự<select value={jobFilters.order || 'desc'} onChange={e => { setJobFilters({ ...jobFilters, order: e.target.value }); setPage(1); }}><option value="desc">Giảm dần</option><option value="asc">Tăng dần</option></select></label>
      </div>
      <Panel
        title="Danh sách việc làm"
        subtitle={`${query.data?.meta.total || 0} tin phù hợp · phân trang tại backend`}
      >
        <Status query={query}>
          <Table
            rows={query.data?.data || []}
            columns={[
              {
                name: "Vị trí",
                render: (r) => (
                    <button className="text-button" onClick={async () => {
                      try { const result = await api('/jobs/' + encodeURIComponent(r._id) + '?dataset_version=' + encodeURIComponent(query.data?.meta.dataset_version)); setDetail(result.data); }
                      catch (error) { window.dispatchEvent(new CustomEvent('app-notice', { detail: (error as Error).message })); }
                    }}>
                    {r.job_title}
                  </button>
                ),
              },
              { name: "Doanh nghiệp", render: (r) => r.company_name },
              { name: "Địa phương", render: (r) => r.province },
              {
                name: "Kinh nghiệm",
                render: (r) => r.experience_years == null ? "Chưa rõ" : r.experience_years + " năm",
              },
              { name: "Lương / tháng", render: (r) => money(r.salary_mid_vnd) },
            ]}
          />
        </Status>
        <div className="pagination">
          <button disabled={page === 1} onClick={() => setPaging({ signature, page: 1, cursors: [''] })}>Trang đầu</button>
          <button disabled={page === 1} onClick={() => setPage(page - 1)}>
            Trước
          </button>
          <span>Trang {page}</span>
          <button
            disabled={!query.data?.meta.next_cursor}
            onClick={() => setPaging({ signature, page: page + 1, cursors: [...cursors.slice(0, page), query.data.meta.next_cursor] })}
          >
            Sau
          </button>
        </div>
      </Panel>
      {detail && (
        <DetailDialog onClose={() => setDetail(null)}>
            <button
              className="close"
              aria-label="Đóng chi tiết"
              onClick={() => setDetail(null)}
            >
              ×
            </button>
            <h2>{detail.job_title}</h2>
            <p>
              {detail.company_name} · {detail.province}
            </p>
            <strong>{money(detail.salary_mid_vnd)}</strong>
            <p className="muted">
              {detail.salary_original_text} · {detail.salary_quality_status}
            </p>
            <p>{detail.required_skills.join(" · ")}</p>
            <div className="job-description">{detail.job_description || 'Nguồn không cung cấp mô tả.'}</div>
            {/^https?:\/\//.test(detail.source_url) && (
              <a href={detail.source_url} target="_blank" rel="noreferrer">
                Mở tin gốc ↗
              </a>
            )}
            <div className="data-foot">Raw ref: {detail.raw_record_ref}</div>
        </DetailDialog>
      )}
    </>
  );
}
function Datasets() {
  const client = useQueryClient(),
    query = useData("/datasets", false, true);
  const [file, setFile] = useState<File | null>(null),
    [source, setSource] = useState("DEMO"),
    [demo, setDemo] = useState(true),
    [notice, setNotice] = useState(""),
    [quality, setQuality] = useState<Row | null>(null);
  const [sourceMetadata, setSourceMetadata] = useState<Record<string, string>>({});
  const [files, setFiles] = useState<File[]>([]), [preview, setPreview] = useState(''), [confirmed, setConfirmed] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const uploadKeys = React.useRef(new Map<string, string>());
  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw Error("Hãy chọn file dữ liệu.");
      if (!confirmed) throw Error('Hãy kiểm tra preview và xác nhận nguồn trước khi gửi.');
      if (files.some(f => f.size > 50 * 1024 * 1024)) throw Error('Mỗi file tối đa 50 MiB; chia JSONL thành các chunk nhỏ hơn.');
      const metadata = {
        source_type: demo ? 'synthetic' : 'upload', dataset_origin: demo ? 'synthetic' : 'public_unverified',
        permission_status: demo ? 'SYNTHETIC_FIXTURE' : 'DECLARED_PERMISSION',
        ...Object.fromEntries(Object.entries(sourceMetadata).filter(([, value]) => value.trim())),
      };
      const signature = JSON.stringify({ files: files.map(f => [f.name, f.size, f.lastModified]), source, demo, metadata });
      if (!uploadKeys.current.has(signature)) uploadKeys.current.set(signature, crypto.randomUUID());
      const idempotencyKey = uploadKeys.current.get(signature)!;
      if (!demo && !sourceMetadata.permission_evidence?.trim()) throw Error('Cần ghi bằng chứng quyền sử dụng nguồn ngoài.');
      if (files.length > 1) {
        if (files.some(f => !f.name.toLowerCase().endsWith('.jsonl'))) throw Error('Staged import chỉ nhận các chunk JSONL.');
        const chunks = [];
        for (const f of files) {
          setUploadProgress('Đang kiểm tra ' + f.name);
          const bytes = await f.arrayBuffer();
          const digest = await crypto.subtle.digest('SHA-256', bytes);
          const sha256 = Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
          const text = new TextDecoder().decode(bytes);
          let row_count = 0, start = 0;
          while (start < text.length) {
            const newline = text.indexOf('\n', start), end = newline < 0 ? text.length : newline;
            if (text.slice(start, end).trim()) row_count++;
            if (row_count > 500000) throw Error('Mỗi chunk tối đa 500.000 dòng; chia file thành các chunk nhỏ hơn.');
            start = end + 1;
          }
          chunks.push({ sha256, bytes: f.size, row_count });
        }
        const staged = await api('/datasets/staged', { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ source, is_demo: demo, source_metadata: metadata, chunks }) });
        const version = staged.data.dataset_version;
        const state = await api('/datasets/' + version);
        if (state.data.sealed) return api(`/datasets/staged/${version}/complete`, { method: 'POST' });
        for (let i = 0; i < files.length; i++) {
          setUploadProgress(`Đang gửi chunk ${i + 1}/${files.length}`);
          const payload = new FormData(); payload.append('file', files[i]);
          await api(`/datasets/staged/${version}/chunks/${i}`, { method: 'PUT', body: payload });
        }
        return api(`/datasets/staged/${version}/complete`, { method: 'POST' });
      }
      const data = new FormData();
      data.append("file", file);
      data.append("source", source);
      data.append("is_demo", String(demo));
      data.append("source_metadata", JSON.stringify(metadata));
      return api("/datasets/upload", {
        method: "POST",
        body: data,
        headers: { "Idempotency-Key": idempotencyKey },
      });
    },
    onSuccess: (r) => {
      setNotice("Đã nhận file. Ingestion job: " + r.data.job_id);
      setUploadProgress('Đã gửi; theo dõi tiến độ ở Giám sát ETL.');
      client.invalidateQueries();
    },
    onError: (e) => setNotice(e.message),
  });
  async function run(version: string) {
    try {
      const r = await api("/etl/jobs", {
        method: "POST",
        body: JSON.stringify({ dataset_version: version }),
      });
      setNotice("Đã tạo ETL job: " + r.data.job_id);
      client.invalidateQueries();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  return (
    <>
      <section className="upload-panel">
        <div className="upload-symbol">
          <Upload />
        </div>
        <div>
          <h2>Nhập dữ liệu tuyển dụng</h2>
          <p className="muted">
            CSV, JSON hoặc JSONL · UTF-8 · tối đa 50 MiB. Dữ liệu gốc được lưu
            để truy vết.
          </p>
          <div className="upload-fields">
            {[
              ["license_permission", "Giấy phép / quyền sử dụng (nếu có)", "text"],
              ["collected_at", "Ngày thu thập (nếu biết)", "date"],
              ["observation_from", "Bắt đầu quan sát (nếu biết)", "date"],
              ["observation_to", "Kết thúc quan sát (nếu biết)", "date"],
              ["permission_evidence", "Bằng chứng quyền sử dụng nguồn ngoài", "text"],
              ["source_revision", "Revision nguồn (nếu có)", "text"],
              ["adapter_version", "Phiên bản adapter (nếu có)", "text"],
            ].map(([key, label, type]) => <label key={key}>{label}<input type={type} aria-label={label} value={sourceMetadata[key] || ""} onChange={(e) => setSourceMetadata({ ...sourceMetadata, [key]: e.target.value })} /></label>)}
            <input
              type="file"
              aria-label="Chọn dataset"
              accept=".csv,.json,.jsonl"
              multiple
              onChange={async (e) => {
                const selected = Array.from(e.target.files || []); setFiles(selected); setFile(selected[0] || null); setConfirmed(false);
                setPreview(selected[0] ? await selected[0].slice(0, 4096).text() : '');
              }}
            />
            <input
              aria-label="Nguồn dữ liệu"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              required
              maxLength={100}
            />
            <label className="checkbox">
              <input
                type="checkbox"
                checked={demo}
                onChange={(e) => setDemo(e.target.checked)}
              />{" "}
              Dữ liệu DEMO
            </label>
            <Button
              disabled={!file || !confirmed || upload.isPending || !source.trim()}
              onClick={() => upload.mutate()}
            >
              <Upload size={16} />{" "}
              {upload.isPending ? "Đang tải…" : "Upload dataset"}
            </Button>
          </div>
          {file && <div className="import-preview"><h3>1 · Kiểm tra dữ liệu</h3><div>{files.length} file · {files.reduce((n, f) => n + f.size, 0).toLocaleString('vi-VN')} bytes</div><pre className="json-report">{preview}</pre><div className="muted">Tên cột chuẩn: job_title, company_name, salary, source_job_id, province, industry, posted_year. Nguồn Tinix/VietJobs cần chuyển qua adapter trước khi nhập.</div>
            <h3>2 · Xác nhận nguồn</h3><label className="checkbox"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Tôi đã kiểm tra schema, quyền sử dụng và nhãn DEMO/nguồn ngoài.</label>
            <div role="status">{uploadProgress}</div><div className="data-foot">3 · Gửi → ingestion → chạy ETL → kiểm tra quality → công bố nếu đạt. Không tạo ngày đăng từ năm.</div></div>}
        </div>
      </section>
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <Panel
        title="Dataset versions"
      >
        <Status query={query}>
          <Table
            rows={query.data?.data || []}
            columns={[
              {
                name: "Version",
                render: (r) => (
                  <>
                    <ShortId id={r._id} />
                    {r.is_demo && <span className="mini-demo">DEMO</span>}
                  </>
                ),
              },
              { name: "Nguồn", render: (r) => r.source },
              {
                name: "Trạng thái",
                render: (r) => <Badge status={r.status} />,
              },
              {
                name: "Raw / Clean",
                render: (r) =>
                  `${r.row_counts.raw ?? "—"} / ${r.row_counts.clean ?? "—"}`,
              },
              {
                name: "Thao tác",
                render: (r) => (
                  <div className="actions">
                    {["RAW_READY", "FAILED"].includes(r.status) && (
                      <button onClick={() => run(r._id)}>
                        <Play size={13} /> ETL
                      </button>
                    )}
                    <button
                      onClick={async () => {
                        try {
                        const result = await api(
                          "/datasets/" + r._id + "/quality",
                        );
                        setQuality(
                          result.data || {
                            dataset_version: r._id,
                            message: "Chưa có báo cáo. Hãy chạy ETL.",
                          },
                        );
                        } catch (error) { setNotice((error as Error).message); }
                      }}
                    >
                      Chất lượng
                    </button>
                  </div>
                ),
              },
            ]}
          />
        </Status>
      </Panel>
      {quality && (
        <Panel title="Báo cáo chất lượng">
          <button className="text-button" onClick={() => setQuality(null)}>
            Đóng báo cáo
          </button>
          <pre className="json-report">{JSON.stringify(quality, null, 2)}</pre>
          {quality.counts && (
            <QualityRecords version={quality.dataset_version} />
          )}
        </Panel>
      )}
    </>
  );
}
function ETL() {
  const query = useData("/etl/jobs", false, true);
  const client = useQueryClient();
  const [notice, setNotice] = useState("");
  async function action(id: string, verb: string) {
    try {
      await api("/etl/jobs/" + id + "/" + verb, { method: "POST", body: "{}" });
      client.invalidateQueries();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  return (
    <>
      {notice && (
        <div className="error" role="alert">
          {notice}
        </div>
      )}
      <Panel
        title="Giám sát tác vụ"
      >
        <Status query={query}>
          <Table
            rows={query.data?.data || []}
            columns={[
              { name: "Job", render: (r) => <ShortId id={r._id} /> },
              { name: "Loại", render: (r) => r.job_type },
              {
                name: "Trạng thái",
                render: (r) => <Badge status={r.status} />,
              },
              {
                name: "Thời gian",
                render: (r) =>
                  r.started_at
                    ? new Date(r.started_at).toLocaleString("vi-VN")
                    : "Chờ worker",
              },
              {
                name: "Kết quả / Lỗi",
                render: (r) =>
                  r.error?.message ||
                  (r.metrics?.counts
                    ? `${r.metrics.counts.clean} clean / ${r.metrics.counts.invalid} invalid`
                    : r.metrics?.raw_records
                      ? `${r.metrics.raw_records} raw`
                      : r.metrics?.models
                        ? `${r.metrics.models.length} models`
                        : "—"),
              },
              {
                name: "Duration / Throughput",
                render: (r) => (
                  <>
                    {r.started_at
                      ? Math.max(
                          0,
                          (new Date(r.finished_at || Date.now()).getTime() -
                            new Date(r.started_at).getTime()) /
                            1000,
                        ).toFixed(1) + " s"
                      : "—"}
                    <br />
                    <small className="muted">
                      {r.metrics?.elapsed_seconds && r.metrics?.counts
                        ? Math.round(
                            r.metrics.counts.raw / r.metrics.elapsed_seconds,
                          ).toLocaleString("vi-VN") + " dòng/s"
                        : "—"}
                    </small>
                  </>
                ),
              },
              {
                name: "Thao tác",
                render: (r) => (
                  <div className="actions">
                    {r.status === "FAILED" && (
                      <button onClick={() => action(r._id, "retry")}>
                        Retry
                      </button>
                    )}
                    {["QUEUED", "RUNNING"].includes(r.status) && (
                      <button onClick={() => action(r._id, "cancel")}>
                        Hủy
                      </button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        </Status>
      </Panel>
    </>
  );
}
function Models() {
  const role = useContext(Context).role;
  const [version, setVersion] = useState(""),
    [notice, setNotice] = useState(""),
    [detail, setDetail] = useState<Row | null>(null);
  const query = useData(
      "/models?page_size=100&dataset_version=" + version,
      false,
      true,
    ),
    datasets = useData("/datasets");
  const client = useQueryClient();
  async function train() {
    try {
      const r = await api("/models/train", {
        method: "POST",
        body: JSON.stringify({ dataset_version: version }),
      });
      setNotice("Đã tạo training job: " + r.data.job_id);
      client.invalidateQueries();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  return (
    <>
      <div className="command-bar">
        <select
          aria-label="Dataset huấn luyện"
          value={version}
          onChange={(e) => setVersion(e.target.value)}
        >
          <option value="">Chọn dataset đã công bố</option>
          {(datasets.data?.data || [])
            .filter((r: Row) => r.status === "PUBLISHED")
            .map((r: Row) => (
              <option key={r._id} value={r._id}>
                {r.source} · {r._id.slice(0, 8)}
              </option>
            ))}
        </select>
        {role === "ADMIN" && (
          <Button disabled={!version} onClick={train}>
            <Play size={16} /> Huấn luyện models
          </Button>
        )}
      </div>
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <Panel
        title="Model registry"
      >
        <Status query={query}>
          <Table
            rows={query.data?.data || []}
            columns={[
              {
                name: "Mô hình",
                render: (r) => (
                  <div>
                    <strong>{r.algorithm}</strong>
                    <div className="muted">
                      <ShortId id={r._id} />
                      {r.is_demo ? " · DEMO" : ""}
                    </div>
                  </div>
                ),
              },
              {
                name: "Validation MAE",
                render: (r) => money(r.validation_metrics.mae),
              },
              {
                name: "Dataset",
                render: (r) => <ShortId id={r.dataset_version} />,
              },
              {
                name: "N train / val / test",
                render: (r) =>
                  r.sample_counts
                    ? `${r.sample_counts.train} / ${r.sample_counts.validation} / ${r.sample_counts.test}`
                    : "—",
              },
              {
                name: "Test MAE / RMSE",
                render: (r) => (
                  <>
                    {money(r.test_metrics.mae)}
                    <br />
                    <small className="muted">
                      {money(r.test_metrics.rmse)}
                    </small>
                  </>
                ),
              },
              {
                name: "Test R²",
                render: (r) => r.test_metrics.r2?.toFixed(3) ?? "—",
              },
              { name: "Test MedAE (VND)", render: (r) => money(r.test_metrics.median_absolute_error) },
              { name: "Nhóm thí nghiệm", render: (r) => r.algorithm === "spark_linear_numeric" ? "Spark · kinh nghiệm quan sát được" : "Local · cùng sample/split/features" },
              {
                name: "Trạng thái",
                render: (r) =>
                  r.is_active ? (
                    <Badge status="ACTIVE" />
                  ) : r.selected_by_validation ? (
                    <span className="badge green">Validation winner</span>
                  ) : (
                    <Badge status={r.status} />
                  ),
              },
              {
                name: "Thao tác",
                render: (r) => (
                  <div className="actions">
                    <button
                      onClick={async () => {
                        try {
                        const result = await api(
                          "/models/" + r._id + "/metrics",
                        );
                        setDetail(result.data);
                        } catch (error) { setNotice((error as Error).message); }
                      }}
                    >
                      Metrics
                    </button>
                    {role === "ADMIN" &&
                      !r.is_active &&
                      r.algorithm !== "baseline" && (
                        <button
                          onClick={async () => {
                            try {
                              await api("/models/" + r._id + "/activate", {
                                method: "POST",
                                body: "{}",
                              });
                              setNotice("Đã active model " + r._id);
                              client.invalidateQueries();
                            } catch (e) {
                              setNotice((e as Error).message);
                            }
                          }}
                        >
                          Active
                        </button>
                      )}
                  </div>
                ),
              },
            ]}
          />
        </Status>
      </Panel>
      {detail && (
        <Panel title="Experiment và split manifest">
          <button className="text-button" onClick={() => setDetail(null)}>
            Đóng
          </button>
          <pre className="json-report">{JSON.stringify(detail, null, 2)}</pre>
          <ModelDiagnostics id={detail._id} />
        </Panel>
      )}
    </>
  );
}
const predictionSchema = z.object({
  job_title: z.string().trim().min(1, "Nhập vị trí công việc"),
  industry: z.string().min(1),
  province: z.string().min(1),
  experience_years: z.coerce.number().min(0).max(60),
  skills: z.string(),
});
type PredictionForm = z.infer<typeof predictionSchema>;
function Predictions() {
  const form = useForm<PredictionForm>({
    resolver: zodResolver(predictionSchema),
    defaultValues: {
      job_title: "Data Engineer",
      industry: "Information Technology",
      province: "Hồ Chí Minh",
      experience_years: 3,
      skills: "python, sql",
    },
  });
  const [result, setResult] = useState<Row | null>(null),
    [error, setError] = useState("");
  const history = useData("/predictions/history");
  const client = useQueryClient();
  async function submit(values: PredictionForm) {
    setError("");
    try {
      const { skills, ...rest } = values;
      const r = await api("/predictions/salary", {
        method: "POST",
        body: JSON.stringify({
          ...rest,
          required_skills: skills
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      });
      setResult(r.data);
      client.invalidateQueries();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="prediction-grid">
        <Panel
          title="Thông tin công việc"
        >
          <form
            className="prediction-form"
            onSubmit={form.handleSubmit(submit)}
          >
            {[
              { key: "job_title", label: "Vị trí công việc" },
              { key: "industry", label: "Ngành nghề" },
              { key: "province", label: "Địa phương" },
              { key: "experience_years", label: "Kinh nghiệm (năm)" },
              { key: "skills", label: "Kỹ năng (phân cách bằng dấu phẩy)" },
            ].map((f) => (
              <label key={f.key}>
                {f.label}
                <input
                  {...form.register(f.key as keyof PredictionForm)}
                  type={f.key === "experience_years" ? "number" : "text"}
                  step={f.key === "experience_years" ? "0.5" : undefined}
                />
                {form.formState.errors[f.key as keyof PredictionForm] && (
                  <small className="field-error">
                    {
                      form.formState.errors[f.key as keyof PredictionForm]
                        ?.message
                    }
                  </small>
                )}
              </label>
            ))}
            {error && (
              <div className="error" role="alert">
                {error}
              </div>
            )}
            <Button disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting
                ? "Đang dự đoán…"
                : "Dự đoán mức lương"}{" "}
              <ArrowRight size={16} />
            </Button>
          </form>
        </Panel>
        <Panel title="Kết quả dự đoán">
          {result ? (
            <div className="prediction-result">
              <span className="small-icon">
                <Coins />
              </span>
              <p>Lương ước lượng mỗi tháng</p>
              <strong>{money(result.predicted_salary_vnd)}</strong>
              <span className="muted">VND / tháng</span>
              <div className="data-foot">
                Model <ShortId id={result.model_version} /> · Test MAE{" "}
                {money(result.model_metrics.mae)}
                <br />Dataset <ShortId id={result.dataset_version} />
              </div>
              {result.reference_period?.from && (
                <small className="muted">
                  Dữ liệu tham chiếu:{" "}
                  {new Date(result.reference_period.from).toLocaleDateString(
                    "vi-VN",
                  )}{" "}
                  –{" "}
                  {new Date(result.reference_period.to).toLocaleDateString(
                    "vi-VN",
                  )}
                </small>
              )}
              {result.warnings.map((w: string) => (
                <div key={w} className="demo-notice">
                  {w === "DEMO_MODEL_NOT_MARKET_ESTIMATE"
                    ? "DEMO: mô hình học từ dữ liệu tổng hợp, không dùng như ước lượng thị trường thực."
                    : ({
                        UNSEEN_JOB_TITLE: "Chức danh chưa xuất hiện trong dữ liệu huấn luyện.",
                        UNSEEN_INDUSTRY: "Ngành nghề chưa xuất hiện trong dữ liệu huấn luyện.",
                        UNSEEN_PROVINCE: "Địa phương chưa xuất hiện trong dữ liệu huấn luyện.",
                        UNSEEN_SENIORITY_LEVEL: "Cấp bậc chưa xuất hiện trong dữ liệu huấn luyện.",
                        UNSEEN_EDUCATION_LEVEL: "Trình độ chưa xuất hiện trong dữ liệu huấn luyện.",
                        UNSEEN_EMPLOYMENT_TYPE: "Loại hình công việc chưa xuất hiện trong dữ liệu huấn luyện.",
                        UNSEEN_REMOTE_TYPE: "Hình thức làm việc chưa xuất hiện trong dữ liệu huấn luyện.",
                        EXPERIENCE_OUTSIDE_TRAINING_RANGE: "Kinh nghiệm nằm ngoài khoảng quan sát khi huấn luyện; cần thận trọng khi diễn giải.",
                        NO_OBSERVED_TRAINING_EXPERIENCE: "Tập huấn luyện chưa có kinh nghiệm quan sát được để đối chiếu đầu vào này.",
                        ACTIVE_ARTIFACT_FAILED_USING_PREVIOUS_MODEL: "Mô hình hiện hành không khả dụng; kết quả dùng phiên bản trước đã kiểm tra.",
                      } as Record<string, string>)[w] || w}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty">
              Nhập thông tin và gửi yêu cầu để xem kết quả từ model.
            </div>
          )}
        </Panel>
      </div>
      <Panel title="Lịch sử dự đoán">
        <Status query={history}>
          <Table
            rows={history.data?.data || []}
            columns={[
              {
                name: "Thời gian",
                render: (r) => new Date(r.created_at).toLocaleString("vi-VN"),
              },
              { name: "Vị trí", render: (r) => r.input_features.job_title },
              {
                name: "Mức lương / tháng",
                render: (r) => money(r.predicted_salary_vnd),
              },
              {
                name: "Model version",
                render: (r) => <ShortId id={r.model_version} />,
              },
            ]}
          />
        </Status>
      </Panel>
    </>
  );
}
function Settings() {
  const query = useData("/system/status", false, true);
  return (
    <>
      <Panel
        title="Trạng thái hệ thống"
      >
        <Status query={query}>
          <div className="system-summary">
            <CheckCircle2 /> MongoDB: {query.data?.data.mongodb} ·{" "}
            {query.data?.data.database}
          </div>
          <Table
            rows={query.data?.data.workers || []}
            columns={[
              { name: "Worker", render: (r) => r.id },
              { name: "Loại", render: (r) => r.kind },
              {
                name: "Heartbeat",
                render: (r) => new Date(r.updated_at).toLocaleString("vi-VN"),
              },
            ]}
          />
          <div className="panel-links">
            <a href="/docs" target="_blank" rel="noreferrer">
              FastAPI / Swagger ↗
            </a>
            <a href="http://localhost:8081" target="_blank" rel="noreferrer">
              Spark Master UI ↗
            </a>
          </div>
        </Status>
      </Panel>
      <ConfigPanel />
      <Benchmarks />
    </>
  );
}
export default function Workspace({ role }: { role: string }) {
  const [params, setParams] = useSearchParams();
  const version = params.get('dataset_version') || '', province = params.get('province') || '', industry = params.get('industry') || '',
    postedFrom = params.get('posted_from') || '', postedTo = params.get('posted_to') || '';
  function updateFilters(changes: Record<string, string>) {
    setParams(previous => { const next = new URLSearchParams(previous); Object.entries(changes).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key)); return next; });
  }
  const datasets = useQuery({
    queryKey: ["versions"],
    queryFn: () => api("/datasets"),
    refetchInterval: 8000,
  });
  const options = useQuery({
    queryKey: ["filter-options", version],
    queryFn: () =>
      api(
        "/jobs/filters/options" +
          (version ? "?dataset_version=" + version : ""),
      ),
    retry: false,
    refetchInterval: 8000,
  });
  const location = useLocation();
  const names: Record<string, string> = {
    "/": "Dashboard tổng quan",
    "/analytics/recruitment": "Phân tích tuyển dụng",
    "/analytics/salary": "Phân tích mức lương",
    "/jobs": "Khám phá việc làm",
    "/datasets": "Quản lý dữ liệu",
    "/etl": "Giám sát ETL",
    "/models": "Machine Learning",
    "/predictions": "Dự đoán mức lương",
    "/settings": "Hệ thống",
    "/sources": "Nguồn dữ liệu & quyền sử dụng",
    "/quality": "Chất lượng theo phiên bản",
    "/users": "Quản trị người dùng",
    "/audit": "Nhật ký quản trị",
    '/profile': 'Hồ sơ cá nhân',
  };
  const showFilters = [
    "/",
    "/analytics/recruitment",
    "/analytics/salary",
    "/jobs",
  ].includes(location.pathname);
  if (!can(role, routePermission[location.pathname.toLowerCase().replace(/\/+$/, '')] || 'read')) return <Forbidden />;
  return (
    <Context.Provider
      value={{ version, province, industry, role, postedFrom, postedTo }}
    >
      <PageHeader title={names[location.pathname] || "Trang không tồn tại"}>
        <span className="badge">
          <span className="dot" /> Dữ liệu từ API
        </span>
      </PageHeader>
      {showFilters && (
        <FilterToolbar>
          <Filter size={17} />
          <select
            aria-label="Dataset version"
            value={version}
            onChange={(e) => {
              updateFilters({ dataset_version: e.target.value, province: '', industry: '', posted_from: '', posted_to: '' });
            }}
          >
            <option value="">Dataset đang active</option>
            {(datasets.data?.data || [])
              .filter((r: Row) => r.status === "PUBLISHED")
              .map((r: Row) => (
                <option key={r._id} value={r._id}>
                  {r.source} · {r._id.slice(0, 8)}
                </option>
              ))}
          </select>
          <select
            aria-label="Địa phương"
            value={province}
            onChange={(e) => updateFilters({ province: e.target.value })}
          >
            <option value="">Tất cả địa phương</option>
            {(options.data?.data.provinces || []).map((p: string) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <select
            aria-label="Ngành nghề"
            value={industry}
            onChange={(e) => updateFilters({ industry: e.target.value })}
          >
            <option value="">Tất cả ngành nghề</option>
            {(options.data?.data.industries || []).map((p: string) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <label>
            Từ ngày
            <input
              aria-label="Từ ngày"
              type="date"
              value={postedFrom}
              onChange={(e) => updateFilters({ posted_from: e.target.value })}
            />
          </label>
          <label>
            Đến ngày
            <input
              aria-label="Đến ngày"
              type="date"
              value={postedTo}
              onChange={(e) => updateFilters({ posted_to: e.target.value })}
            />
          </label>
        </FilterToolbar>
      )}
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analytics/recruitment" element={<Analysis />} />
        <Route path="/analytics/salary" element={<Analysis salary />} />
        <Route path="/jobs" element={<JobList />} />
        <Route path="/datasets" element={<PermissionGate role={role} permission="manage"><Datasets /></PermissionGate>} />
        <Route path="/etl" element={<PermissionGate role={role} permission="manage"><ETL /></PermissionGate>} />
        <Route path="/models" element={<PermissionGate role={role} permission="predict"><Models /></PermissionGate>} />
        <Route path="/predictions" element={<PermissionGate role={role} permission="predict"><Predictions /></PermissionGate>} />
        <Route path="/settings" element={<PermissionGate role={role} permission="manage"><Settings /></PermissionGate>} />
        <Route path="/users" element={<PermissionGate role={role} permission="manage"><AdminUsers /></PermissionGate>} />
        <Route path="/audit" element={<PermissionGate role={role} permission="manage"><AuditLogs /></PermissionGate>} />
        <Route path="/sources" element={<PermissionGate role={role} permission="manage"><Sources /></PermissionGate>} />
        <Route path="/quality" element={<PermissionGate role={role} permission="manage"><QualityDashboard /></PermissionGate>} />
        <Route path="/profile" element={<Profile />} />
        <Route path="*" element={<Link to="/">Quay lại Dashboard</Link>} />
      </Routes>
    </Context.Provider>
  );
}

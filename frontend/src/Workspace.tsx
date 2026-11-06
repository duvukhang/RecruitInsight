import { Button } from "./components/ui/button";
import ConfigPanel from "./ConfigPanel";
import { QualityRecords, Benchmarks, ModelDiagnostics } from "./ExtraReports";
import React, { createContext, useContext, useState } from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
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
function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}
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
function ObservationScope({ meta }: { meta?: Row }) {
  const filters = useContext(Context);
  if (!meta) return null;
  const period = meta.reference_period;
  return (
    <div className="data-foot">
      {meta.is_demo && <div className="demo-notice">DEMO · Dữ liệu tổng hợp, không đại diện thị trường lao động thực.</div>}
      Dataset <ShortId id={meta.dataset_version} /> · {meta.sample_size} tin · {meta.eligible_count} nhãn lương · Thiếu nhãn: {meta.missing_salary_rate == null ? "—" : (100 * meta.missing_salary_rate).toFixed(1) + "%"}
      <br />
      Ngày đăng quan sát: {period?.from ? `${period.from.slice(0, 10)} – ${period.to?.slice(0, 10)}` : "Chưa có ngày đăng hợp lệ"} · Địa phương: {filters.province || "Tất cả"} · Ngành: {filters.industry || "Tất cả"} · Ngày lọc: {filters.postedFrom || "Mở"} – {filters.postedTo || "Mở"}
      <p>Số tin chỉ mô tả tập dữ liệu quan sát. Lương công bố (VND/tháng) có thể khác lương thực nhận; quan hệ đồng xuất hiện không chứng minh nguyên nhân.</p>
    </div>
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
  const overview = useData("/analytics/overview", true),
    trends = useData("/analytics/job-trends", true),
    industry = useData("/analytics/salary-by-industry", true),
    skills = useData("/analytics/top-skills", true);
  const data = overview.data?.data;
  const meta = overview.data?.meta;
  return (
    <Status query={overview}>
      {data && (
        <>
          {meta.is_demo && (
            <div className="demo-notice">
              DEMO · Dữ liệu tổng hợp để kiểm thử, không đại diện thị trường
              tuyển dụng thực.
            </div>
          )}
          {meta.warnings?.includes("SMALL_SAMPLE") && (
            <div className="demo-notice">
              Mẫu dưới 30 tin. Xem số mẫu trước khi diễn giải kết quả.
            </div>
          )}
          {meta.warnings?.includes("HIGH_MISSING_SALARY_LABEL_RATE") && (
            <div className="demo-notice">
              Hơn 50% tin chưa đủ nhãn lương chuẩn hóa; phân tích lương chỉ dùng
              phần có nhãn hợp lệ.
            </div>
          )}
          <div className="stat-grid four">
            {[
              {
                label: "Tổng tin tuyển dụng",
                value: data.total_jobs?.toLocaleString("vi-VN"),
                icon: BriefcaseBusiness,
                note: "Tin đã làm sạch, loại trùng",
              },
              {
                label: "Doanh nghiệp",
                value: data.total_companies,
                icon: Building2,
                note: "Trong dataset đang chọn",
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
                note: "Coverage của dữ liệu lương",
              },
            ].map((s) => (
              <article className="stat" key={s.label}>
                <s.icon />
                <span>{s.label}</span>
                <strong>{s.value}</strong>
                <small>{s.note}</small>
              </article>
            ))}
          </div>
          <div className="chart-grid">
            <Panel
              title="Số tin thay đổi thế nào theo tháng?"
              subtitle="Số tin theo tháng đăng tuyển"
            >
              <Status query={trends}>
                <Chart
                  labels={(trends.data?.data || []).map((r: Row) => r.month)}
                  values={(trends.data?.data || []).map((r: Row) => r.count)}
                  type="line"
                />
              </Status>
            </Panel>
            <Panel
              title="Ngành nào xuất hiện nhiều tin nhất?"
              subtitle="Số tin trong tập dữ liệu đã xử lý"
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
            subtitle="Mỗi tin chỉ được đếm một lần cho một kỹ năng"
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
          <div className="data-foot">
            Dataset <ShortId id={meta.dataset_version} /> · {meta.sample_size}{" "}
            mẫu · {meta.method} · Cập nhật{" "}
            {new Date(meta.updated_at).toLocaleString("vi-VN")}
          </div>
          <p className="muted">{data.total_industries ?? "—"} ngành · {data.total_provinces ?? "—"} địa phương có thông tin.</p>
          <div className="panel-links">
            <Link to="/analytics/recruitment">Phân tích tin tuyển dụng</Link>
            <Link to="/analytics/salary">Khảo sát mức lương</Link>
            <Link to="/models">Đánh giá mô hình</Link>
            <Link to="/predictions">Dự đoán mức lương</Link>
          </div>
          <ObservationScope meta={meta} />
        </>
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
      <Status query={overview}><ObservationScope meta={overview.data?.meta} /></Status>
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
          subtitle="Tính trên tin có nhãn lương chuẩn hóa; percentile approximate"
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
      <Panel title={salary ? "So sánh lương công bố theo ngành" : "Kinh nghiệm liên hệ với lương công bố thế nào?"} subtitle="VND/tháng · trung vị mô tả mẫu quan sát; phân vị nhóm chỉ hiện từ 30 nhãn lương. Không xếp hạng từ nhóm ít mẫu.">
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
  const [page, setPage] = useState(1),
    [q, setQ] = useState(""),
    [search, setSearch] = useState(""),
    [detail, setDetail] = useState<Row | null>(null);
  const query = useData(
    "/jobs?page=" + page + "&q=" + encodeURIComponent(search),
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
          placeholder="Tìm theo tên vị trí…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Button>Tìm kiếm</Button>
      </form>
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
                  <button className="text-button" onClick={() => setDetail(r)}>
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
          <button disabled={page === 1} onClick={() => setPage(page - 1)}>
            Trước
          </button>
          <span>Trang {page}</span>
          <button
            disabled={page * 25 >= (query.data?.meta.total || 0)}
            onClick={() => setPage(page + 1)}
          >
            Sau
          </button>
        </div>
      </Panel>
      {detail && (
        <div className="modal-backdrop" onClick={() => setDetail(null)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Chi tiết tuyển dụng"
            onClick={(e) => e.stopPropagation()}
          >
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
            {/^https?:\/\//.test(detail.source_url) && (
              <a href={detail.source_url} target="_blank" rel="noreferrer">
                Mở tin gốc ↗
              </a>
            )}
            <div className="data-foot">Raw ref: {detail.raw_record_ref}</div>
          </section>
        </div>
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
  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw Error("Hãy chọn file dữ liệu.");
      const data = new FormData();
      data.append("file", file);
      data.append("source", source);
      data.append("is_demo", String(demo));
      data.append("source_metadata", JSON.stringify({
        source_type: demo ? "synthetic" : "upload",
        ...Object.fromEntries(Object.entries(sourceMetadata).filter(([, value]) => value.trim())),
      }));
      return api("/datasets/upload", {
        method: "POST",
        body: data,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
    },
    onSuccess: (r) => {
      setNotice("Đã nhận file. Ingestion job: " + r.data.job_id);
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
            ].map(([key, label, type]) => <label key={key}>{label}<input type={type} aria-label={label} value={sourceMetadata[key] || ""} onChange={(e) => setSourceMetadata({ ...sourceMetadata, [key]: e.target.value })} /></label>)}
            <input
              type="file"
              aria-label="Chọn dataset"
              accept=".csv,.json,.jsonl"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
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
              disabled={!file || upload.isPending || !source.trim()}
              onClick={() => upload.mutate()}
            >
              <Upload size={16} />{" "}
              {upload.isPending ? "Đang tải…" : "Upload dataset"}
            </Button>
          </div>
        </div>
      </section>
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <Panel
        title="Dataset versions"
        subtitle="Raw → Clean → Analytics; mỗi lần xử lý được truy vết bằng attempt"
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
                        const result = await api(
                          "/datasets/" + r._id + "/quality",
                        );
                        setQuality(
                          result.data || {
                            dataset_version: r._id,
                            message: "Chưa có báo cáo. Hãy chạy ETL.",
                          },
                        );
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
        subtitle="Các tác vụ chạy ở worker; giao diện cập nhật mỗi 4 giây"
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
        subtitle="Chọn theo validation; holdout test dùng cho đánh giá cuối. Spark numeric là thí nghiệm scale riêng."
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
                        const result = await api(
                          "/models/" + r._id + "/metrics",
                        );
                        setDetail(result.data);
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
      <p className="muted">Các đầu vào mô tả công việc, kinh nghiệm và kỹ năng. Kết quả ước lượng lương công bố từ dữ liệu huấn luyện, không bảo đảm lương ứng viên nhận được; MAE là sai số trên holdout, không phải khoảng dự đoán cho từng người.</p>
      <div className="prediction-grid">
        <Panel
          title="Thông tin công việc"
          subtitle="Kết quả từ model đang active, được lưu vào lịch sử cá nhân"
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
              <small className="muted">
                Chưa có khoảng dự đoán đã hiệu chuẩn.
              </small>
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
        subtitle="Heartbeat workers và kết nối lưu trữ"
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
  const [version, setVersion] = useState(""),
    [province, setProvince] = useState(""),
    [industry, setIndustry] = useState(""),
    [postedFrom, setPostedFrom] = useState(""),
    [postedTo, setPostedTo] = useState("");
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
  };
  const showFilters = [
    "/",
    "/analytics/recruitment",
    "/analytics/salary",
    "/jobs",
  ].includes(location.pathname);
  return (
    <Context.Provider
      value={{ version, province, industry, role, postedFrom, postedTo }}
    >
      <div className="page-heading">
        <div>
          <div className="eyebrow">WORKSPACE / RECRUITMENT ANALYTICS</div>
          <h1>{names[location.pathname] || "Trang không tồn tại"}</h1>
          <p className="muted">
            Phân tích có nguồn gốc. Kết quả có thể kiểm chứng.
          </p>
        </div>
        <span className="badge">
          <span className="dot" /> Dữ liệu từ API
        </span>
      </div>
      {showFilters && (
        <div className="filter-bar">
          <Filter size={17} />
          <select
            aria-label="Dataset version"
            value={version}
            onChange={(e) => {
              setVersion(e.target.value);
              setProvince("");
              setIndustry("");
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
            onChange={(e) => setProvince(e.target.value)}
          >
            <option value="">Tất cả địa phương</option>
            {(options.data?.data.provinces || []).map((p: string) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <select
            aria-label="Ngành nghề"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
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
              onChange={(e) => setPostedFrom(e.target.value)}
            />
          </label>
          <label>
            Đến ngày
            <input
              aria-label="Đến ngày"
              type="date"
              value={postedTo}
              onChange={(e) => setPostedTo(e.target.value)}
            />
          </label>
        </div>
      )}
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analytics/recruitment" element={<Analysis />} />
        <Route path="/analytics/salary" element={<Analysis salary />} />
        <Route path="/jobs" element={<JobList />} />
        <Route path="/datasets" element={<Datasets />} />
        <Route path="/etl" element={<ETL />} />
        <Route path="/models" element={<Models />} />
        <Route path="/predictions" element={<Predictions />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Link to="/">Quay lại Dashboard</Link>} />
      </Routes>
    </Context.Provider>
  );
}

import { useQuery } from "@tanstack/react-query";
import { api, download } from "./api";
import { Chart, Scatter } from "./Chart";
function safeDownload(path: string, name: string) {
  download(path, name).catch((error) =>
    window.dispatchEvent(
      new CustomEvent("app-notice", { detail: error.message }),
    ),
  );
}
export function ModelDiagnostics({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ["diagnostics", id],
    queryFn: () => api("/models/" + id + "/diagnostics"),
  });
  const data = query.data?.data;
  if (query.isPending) return <p className="muted">Đang tải đánh giá mô hình…</p>;
  if (query.error) return <p role="alert" className="error">{query.error.message} <button onClick={() => query.refetch()}>Thử lại</button></p>;
  const residuals = (data?.holdout || []).map((r: any) => (r.actual - r.predicted) / 1e6);
  const lower = residuals.length ? Math.min(...residuals) : 0;
  const width = residuals.length ? Math.max((Math.max(...residuals) - lower) / 20, 0.01) : 1;
  const bins = Array(20).fill(0);
  residuals.forEach((value: number) => bins[Math.min(19, Math.floor((value - lower) / width))]++);
  return (
    <div className="quality-records">
      <div className="actions">
        <button
          disabled={!data?.available_artifacts?.includes("actual")}
          onClick={() =>
            safeDownload(
              "/models/" + id + "/artifacts/actual",
              "actual-vs-predicted.png",
            )
          }
        >
          Tải Actual vs Predicted
        </button>
        <button
          disabled={!data?.available_artifacts?.includes("residuals")}
          onClick={() =>
            safeDownload(
              "/models/" + id + "/artifacts/residuals",
              "residuals.png",
            )
          }
        >
          Tải Residuals
        </button>
        <button
          disabled={!data?.available_artifacts?.includes("holdout")}
          onClick={() =>
            safeDownload("/models/" + id + "/artifacts/holdout", "holdout.json")
          }
        >
          Tải test predictions
        </button>
      </div>
      {data?.holdout?.length > 0 ? (
        <>
          <h3>Actual vs Predicted · holdout test</h3>
          <Scatter
            points={data.holdout.map((r: any) => [
              r.actual / 1e6,
              r.predicted / 1e6,
            ])}
          />
          <h3>Phân bố sai số actual − predicted</h3>
          <Chart labels={bins.map((_, i) => (lower + i * width).toFixed(2))} values={bins} />
          <h3>Feature importance / |coefficient| (phụ thuộc model)</h3>
          <Chart
            labels={data.importance.map((r: any) => r.feature)}
            values={data.importance.map((r: any) => Math.abs(r.value))}
          />
          <h3>Sai số theo nhóm trên holdout (VND/tháng)</h3>
          {data.slice_metrics?.length ? <div className="table-scroll"><table>
            <thead><tr><th>Chiều</th><th>Nhóm</th><th>N</th><th>MAE</th><th>RMSE</th><th>MedAE</th></tr></thead>
            <tbody>{data.slice_metrics.map((r: any, i: number) => <tr key={i}>
              <td>{r.dimension || "province"}</td><td>{r.group || r.province}</td><td>{r.n}</td>
              <td>{Math.round(r.metrics.mae).toLocaleString("vi-VN")}</td>
              <td>{Math.round(r.metrics.rmse).toLocaleString("vi-VN")}</td>
              <td>{Math.round(r.metrics.median_absolute_error).toLocaleString("vi-VN")}</td>
            </tr>)}</tbody>
          </table></div> : <p className="muted">Chưa có nhóm đủ 30 mẫu hoặc model cũ chưa lưu phân tích nhóm. Không suy ra sai số bằng 0.</p>}
        </>
      ) : (
        <p className="muted">
          Chưa có diagnostics artifact cho phiên bản model này.
        </p>
      )}
    </div>
  );
}
export function QualityRecords({ version }: { version: string }) {
  const invalid = useQuery({
    queryKey: ["invalid", version],
    queryFn: () => api("/datasets/" + version + "/invalid"),
  });
  const duplicates = useQuery({
    queryKey: ["duplicates", version],
    queryFn: () => api("/datasets/" + version + "/duplicates"),
  });
  return (
    <div className="quality-records">
      <div className="actions">
        <button
          onClick={() =>
            safeDownload(
              "/datasets/" + version + "/export/invalid",
              "errors.csv",
            )
          }
        >
          Tải CSV lỗi
        </button>
        <button
          onClick={() =>
            safeDownload(
              "/datasets/" + version + "/export/duplicates",
              "duplicates.csv",
            )
          }
        >
          Tải CSV trùng
        </button>
        <button
          onClick={() =>
            safeDownload("/datasets/" + version + "/export/clean", "clean.csv")
          }
        >
          Tải CSV clean
        </button>
      </div>
      {invalid.error && <p className="error">{invalid.error.message}</p>}
      <h3>Bản ghi lỗi ({invalid.data?.meta.total ?? 0})</h3>
      <table>
        <thead>
          <tr>
            <th>Raw reference</th>
            <th>Mã lỗi</th>
          </tr>
        </thead>
        <tbody>
          {(invalid.data?.data || []).map((r: any) => (
            <tr key={r._id}>
              <td>{r.raw_record_ref}</td>
              <td>{r.error_code}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Bản ghi trùng ({duplicates.data?.meta.total ?? 0})</h3>
      <table>
        <thead>
          <tr>
            <th>Raw reference</th>
            <th>Canonical reference</th>
          </tr>
        </thead>
        <tbody>
          {(duplicates.data?.data || []).map((r: any) => (
            <tr key={r._id}>
              <td>{r.raw_record_ref}</td>
              <td>{r.canonical_raw_ref}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Benchmarks() {
  const query = useQuery({
    queryKey: ["benchmarks"],
    queryFn: () => api("/benchmarks"),
  });
  const benchmark = query.data?.data?.find(
    (r: any) => r.status === "COMPLETED",
  );
  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>Spark benchmark</h2>
        </div>
      </div>
      {query.error ? (
        <p className="error">{query.error.message}</p>
      ) : benchmark ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Số dòng</th>
                <th>Cấu hình</th>
                <th>Median (s)</th>
                <th>Min – Max (s)</th>
                <th>Speedup</th>
              </tr>
            </thead>
            <tbody>
              {benchmark.summary.map((r: any) => (
                <tr key={r.rows + r.configuration}>
                  <td>{r.rows.toLocaleString("vi-VN")}</td>
                  <td>{r.configuration}</td>
                  <td>{r.median_seconds.toFixed(3)}</td>
                  <td>
                    {r.min_seconds.toFixed(3)} – {r.max_seconds.toFixed(3)}
                  </td>
                  <td>{r.speedup_vs_local1.toFixed(2)}×</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="data-foot">
            Run {benchmark._id} · Counts và checksum đã đối soát giữa các cấu
            hình.
          </div>
        </div>
      ) : (
        <div className="empty">Chưa có benchmark hoàn tất.</div>
      )}
    </section>
  );
}

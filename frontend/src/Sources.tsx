import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import { DataSourceBadge, EmptyState, ErrorState, InsightPanel } from './components/insights';
export default function Sources() {
  const sources = useQuery({ queryKey: ['sources'], queryFn: () => api('/sources') });
  const datasets = useQuery({ queryKey: ['versions'], queryFn: () => api('/datasets?page_size=100') });
  const [left, setLeft] = useState(''), [right, setRight] = useState('');
  return <>
    <InsightPanel title="Danh mục nguồn">
      {sources.isPending ? <EmptyState>Đang tải nguồn…</EmptyState> : sources.error ? <ErrorState message={sources.error.message} retry={() => sources.refetch()} /> : <div className="source-grid">{sources.data?.data.map((s: any) => <article className="source-card" key={s.id}>
        <span className="eyebrow">{s.permission_status}</span><h3>{s.dataset}</h3><div>Giấy phép công bố: {s.license || 'Chưa công bố'}</div><div>Adapter: {s.adapter_version}</div>
        <a href={s.url} target="_blank" rel="noreferrer">Kiểm tra dataset card ↗</a>
      </article>)}</div>}
    </InsightPanel>
    <InsightPanel title="So sánh hai phiên bản">
      {datasets.error && <ErrorState message={datasets.error.message} retry={() => datasets.refetch()} />}
      <div className="source-grid">{[[left, setLeft], [right, setRight]].map(([value, setValue], i) => <div key={i}><label>Phiên bản {i + 1}<select value={value as string} onChange={e => (setValue as (v: string) => void)(e.target.value)}><option value="">Chọn phiên bản đã công bố</option>{datasets.data?.data.filter((d: any) => d.status === 'PUBLISHED').map((d: any) => <option key={d._id} value={d._id}>{d.is_demo ? 'DEMO' : 'Nguồn ngoài'} · {d.source} · {d._id.slice(0, 8)}</option>)}</select></label>{value && <VersionSummary version={value as string} />}</div>)}</div>
    </InsightPanel>
  </>;
}
function VersionSummary({ version }: { version: string }) {
  const query = useQuery({ queryKey: ['compare', version], queryFn: () => api('/analytics/overview?dataset_version=' + encodeURIComponent(version)) });
  const industries = useQuery({ queryKey: ['compare-industries', version], queryFn: () => api('/analytics/salary-by-industry?dataset_version=' + encodeURIComponent(version)) });
  if (query.isPending) return <EmptyState>Đang tải thống kê…</EmptyState>;
  if (query.error) return <ErrorState message={query.error.message} retry={() => query.refetch()} />;
  const { data, meta } = query.data;
  function exportReport() {
    const report = { dataset_version: version, scope: 'observed postings only', overview: data, metadata: meta, industries: industries.data?.data };
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'report-' + version + '.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <article className="source-card"><DataSourceBadge demo={meta.is_demo} source={meta.source} permission={meta.source_metadata?.permission_status} />
    <dl><dt>Số tin quan sát</dt><dd>{data.total_jobs?.toLocaleString('vi-VN')}</dd><dt>Doanh nghiệp</dt><dd>{data.total_companies}</dd><dt>Ngành / địa phương</dt><dd>{data.total_industries} / {data.total_provinces}</dd><dt>Nhãn lương</dt><dd>{data.salary_sample_size} · {meta.missing_salary_rate == null ? '—' : (100 * (1 - meta.missing_salary_rate)).toFixed(1) + '%'}</dd><dt>Trung vị (VND/tháng)</dt><dd>{data.median_salary_vnd?.toLocaleString('vi-VN') || '—'}</dd><dt>Ngày đăng quan sát</dt><dd>{meta.reference_period?.from || 'Không có ngày chính xác'}</dd><dt>Giấy phép</dt><dd>{meta.source_metadata?.license_permission || 'Chưa khai báo'}</dd></dl>
    {industries.error && <ErrorState message={industries.error.message} retry={() => industries.refetch()} />}
    <div className="table-scroll"><table><thead><tr><th>Ngành</th><th>Tin</th><th>N lương</th><th>Trung vị VND/tháng</th></tr></thead><tbody>{industries.data?.data.map((r: any) => <tr key={r.industry}><td>{r.industry}</td><td>{r.jobs}</td><td>{r.salary_sample_size}</td><td>{r.median_salary_vnd?.toLocaleString('vi-VN') || '—'}</td></tr>)}</tbody></table></div>
    <button disabled={!industries.data} onClick={exportReport}>Tải báo cáo JSON</button></article>;
}

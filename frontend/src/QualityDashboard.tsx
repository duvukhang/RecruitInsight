import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from './api';
import { QualityRecords } from './ExtraReports';
import { DataSourceBadge, EmptyState, ErrorState, InsightPanel } from './components/insights';
export default function QualityDashboard() {
  const [version, setVersion] = useState('');
  const versions = useQuery({ queryKey: ['quality-versions'], queryFn: () => api('/datasets?page_size=100') });
  const query = useQuery({ queryKey: ['quality-report', version], enabled: !!version, queryFn: () => api(`/datasets/${encodeURIComponent(version)}/quality`) });
  const selected = versions.data?.data.find((r: any) => r._id === version);
  const report = query.data?.data;
  return <><InsightPanel title="Chất lượng theo phiên bản">
    <div className="admin-toolbar"><label>Dataset cần kiểm tra<select value={version} onChange={e => setVersion(e.target.value)}><option value="">Chọn phiên bản</option>{versions.data?.data.map((r: any) => <option key={r._id} value={r._id}>{r.is_demo ? 'DEMO' : 'Nguồn ngoài'} · {r.source} · {r._id.slice(0, 8)}</option>)}</select></label></div>
    {versions.error && <ErrorState message={versions.error.message} retry={() => versions.refetch()} />}
    {!version ? <EmptyState>Chọn một phiên bản để xem đối soát và độ phủ.</EmptyState> : query.isPending ? <EmptyState>Đang tải quality report…</EmptyState> : query.error ? <ErrorState message={query.error.message} retry={() => query.refetch()} /> : !report ? <EmptyState>Chưa có báo cáo. Hãy chạy ETL cho phiên bản này.</EmptyState> : <div className="quality-records">
      <DataSourceBadge demo={selected?.is_demo} source={selected?.source} permission={selected?.source_metadata?.permission_status} />
      <div className={report.passed ? 'notice' : 'error'} role="status">{report.passed ? 'Đạt quality gate' : 'Không đạt quality gate'} · raw {report.counts.raw} = invalid {report.counts.invalid} + duplicate {report.counts.duplicate} + clean {report.counts.clean}</div>
      <dl>{['validity', 'uniqueness', 'completeness', 'consistency', 'salary_label_usability', 'training_eligible_rate', 'timeliness'].map(key => <div key={key}><dt>{({ validity: 'Tính hợp lệ', uniqueness: 'Không trùng', completeness: 'Đầy đủ trường bắt buộc', consistency: 'Nhất quán', salary_label_usability: 'Độ phủ nhãn lương', training_eligible_rate: 'Nhãn hợp lệ cho ML', timeliness: 'Ngày đăng trong 180 ngày' } as Record<string, string>)[key]}</dt><dd>{report[key] == null ? 'Không tính được' : (100 * report[key]).toFixed(1) + '%'}</dd></div>)}</dl>
      <div className="table-scroll"><table><thead><tr><th>Trường</th><th>Thiếu</th><th>Mẫu số raw</th><th>Tỷ lệ thiếu</th></tr></thead><tbody>{Object.entries(report.missing_by_field || {}).map(([key, value]: [string, any]) => <tr key={key}><td>{key}</td><td>{value.missing}</td><td>{value.denominator}</td><td>{value.rate == null ? '—' : (100 * value.rate).toFixed(1) + '%'}</td></tr>)}</tbody></table></div>
      {report.profile && <><h3>Độ phủ nguồn & nhãn</h3><div>Doanh nghiệp: {report.profile.companies} · {report.profile.schema_version >= 2 ? `Ngành có thông tin: ${report.profile.industries} · Địa phương có thông tin: ${report.profile.provinces}` : 'Báo cáo cũ chưa loại Unknown khỏi số ngành/địa phương; xem tỷ lệ thiếu ở trên.'} · Năm có thật: {report.profile.year_from || '—'} – {report.profile.year_to || '—'}</div><pre className="json-report">{JSON.stringify({ salary_parse_status: report.profile.salary_parse_status, source_coverage: report.profile.source_coverage, dataset_origin: report.profile.dataset_origin }, null, 2)}</pre></>}
      <details><summary>Metadata, ngưỡng và định nghĩa chỉ số</summary><pre className="json-report">{JSON.stringify({ attempt_id: report.attempt_id, thresholds: report.thresholds, definitions: report.definitions, source_metadata: report.source_metadata, sha256: selected?.content_hash }, null, 2)}</pre></details>
    </div>}
  </InsightPanel>{report?.counts && <InsightPanel title="Bản ghi lỗi và trùng"><QualityRecords version={version} /></InsightPanel>}</>;
}

import {Button} from "./components/ui/button";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
export default function ConfigPanel() {
  const query = useQuery({
    queryKey: ["normalization-config"],
    queryFn: () => api("/system/settings"),
  });
  const [notice, setNotice] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const rate = fields.get("usd_rate");
    const body = {
      validity_min: Number(fields.get("validity")),
      hours_per_month: fields.get("hours") ? Number(fields.get("hours")) : null,
      days_per_month: fields.get("days") ? Number(fields.get("days")) : null,
      rates: rate
        ? {
            USD: {
              rate: Number(rate),
              source: fields.get("fx_source"),
              date: fields.get("fx_date"),
            },
          }
        : {},
    };
    try {
      await api("/system/settings", {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      setNotice("Đã lưu. Dataset đã công bố giữ nguyên cấu hình cũ.");
      query.refetch();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  const config = query.data?.data;
  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>Quy tắc chuẩn hóa & chất lượng</h2>
          <p className="muted">
            Tỷ giá và giả định thời gian do người dùng cung cấp, được lưu cùng
            mỗi dataset version.
          </p>
        </div>
      </div>
      {query.error ? (
        <div className="error">{query.error.message}</div>
      ) : (
        config && (
          <form
            key={query.dataUpdatedAt}
            className="config-form"
            onSubmit={submit}
          >
            <label>
              Ngưỡng validity (0–1)
              <input
                name="validity"
                type="number"
                min="0"
                max="1"
                step="0.01"
                defaultValue={config.validity_min}
                required
              />
            </label>
            <label>
              Giờ làm / tháng (tùy chọn)
              <input
                name="hours"
                type="number"
                min="1"
                max="744"
                defaultValue={config.hours_per_month ?? ""}
              />
            </label>
            <label>
              Ngày làm / tháng (tùy chọn)
              <input
                name="days"
                type="number"
                min="1"
                max="31"
                defaultValue={config.days_per_month ?? ""}
              />
            </label>
            <label>
              Tỷ giá tham chiếu USD → VND (tùy chọn)
              <input
                name="usd_rate"
                type="number"
                min="1"
                defaultValue={config.rates?.USD?.rate ?? ""}
              />
            </label>
            <label>
              Nguồn tỷ giá
              <input
                name="fx_source"
                placeholder="URL hoặc tài liệu tham chiếu"
                defaultValue={config.rates?.USD?.source ?? ""}
              />
            </label>
            <label>
              Ngày tham chiếu tỷ giá
              <input
                name="fx_date"
                type="date"
                defaultValue={config.rates?.USD?.date ?? ""}
              />
            </label>
            <div className="config-submit">
              <Button>Lưu cấu hình</Button>
            </div>
          </form>
        )
      )}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
    </section>
  );
}

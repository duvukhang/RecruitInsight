let token = "";
let csrf = sessionStorage.getItem("csrf") || "";
let refreshFlight: Promise<void> | null = null;
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
function renew() {
  if (!refreshFlight) {
    refreshFlight = fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "X-CSRF-Token": csrf },
    })
      .then(async (response) => {
        if (!response.ok) throw Error("Expired session");
        remember(await response.json());
      })
      .catch(() => {
        clearSession();
        window.dispatchEvent(new Event("app-session-expired"));
        throw Error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
      })
      .finally(() => {
        refreshFlight = null;
      });
  }
  return refreshFlight;
}
async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
  retried = false,
): Promise<Response> {
  const sentToken = token;
  const response = await fetch("/api/v1" + path, {
    ...init,
    headers: {
      ...(init.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (response.status === 401 && !['/auth/login', '/auth/refresh', '/auth/logout'].includes(path) && !retried) {
    if (sentToken === token) await renew();
    return authenticatedFetch(path, init, true);
  }
  return response;
}
export async function api(path: string, init: RequestInit = {}) {
  const response = await authenticatedFetch(path, init);
  if (
    response.status !== 204 &&
    !response.headers.get("content-type")?.includes("json")
  ) {
    throw Error(
      response.status === 413
        ? "File vượt quá giới hạn upload."
        : "Dịch vụ đang gián đoạn. Vui lòng thử lại.",
    );
  }
  const body = response.status === 204 ? {} : await response.json();
  if (!response.ok)
    throw new ApiError(body.error?.message || "Không thể kết nối dịch vụ.", response.status);
  return body;
}
export function remember(result: {
  data: { access_token: string };
  csrf_token: string;
}) {
  token = result.data.access_token;
  csrf = result.csrf_token;
  sessionStorage.setItem("csrf", csrf);
}
export function clearSession() {
  token = "";
  csrf = "";
  sessionStorage.removeItem("csrf");
}
export function csrfHeaders() {
  return { "X-CSRF-Token": csrf };
}
export async function download(path: string, filename: string) {
  const response = await authenticatedFetch(path);
  if (!response.ok)
    throw Error("Không tải được báo cáo. Kiểm tra trạng thái ETL/model.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  const supplied = response.headers
    .get("Content-Disposition")
    ?.match(/filename="?([^";]+)"?/);
  link.download = supplied?.[1] || filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

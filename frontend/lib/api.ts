import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export async function downloadBlob(
  url: string,
  params?: Record<string, string>,
): Promise<void> {
  const response = await api.get(url, {
    params,
    responseType: "blob",
  });
  const contentDisposition =
    (response.headers["content-disposition"] as string) ?? "";
  const match = contentDisposition.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? "export";
  const contentType =
    (response.headers["content-type"] as string) ?? "application/octet-stream";
  const blob = new Blob([response.data as BlobPart], { type: contentType });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

export default api;

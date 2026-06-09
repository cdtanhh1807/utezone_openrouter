// src/services/FileService.ts
import axiosInstance from "../utils/AxiosInstance";

export interface UploadResponse {
  file_id: string;
  url: string;
  pending_moderation?: boolean;
  media_type?: string;
  moderation_mode?: string;
}

export interface FileUrlResponse {
  url: string;
}

const FileService = {
  /**
   * Upload mặc định: strict moderation.
   * Dùng cho đăng bài hoặc các flow cũ.
   */
  uploadPicture: (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    return axiosInstance
      .post("/file/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((res) => res.data as UploadResponse);
  },

  /**
   * Upload cho comment/reply: defer moderation.
   * Backend upload file ngay và trả file_id.
   * Comment service sẽ kiểm duyệt nền dựa trên file_id này.
   */
  uploadPictureDeferred: (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    return axiosInstance
      .post("/file/upload?defer_moderation=true", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((res) => res.data as UploadResponse);
  },

  /**
   * Lấy presigned URL thật từ file_id.
   * Endpoint backend trả: { url: "http://localhost:9000/..." }
   */
  getFileUrlData: (fileId: string): Promise<FileUrlResponse> => {
    return axiosInstance
      .get(`file/file/${encodeURIComponent(fileId)}`)
      .then((res) => res.data as FileUrlResponse);
  },

  /**
   * Chỉ build URL API /file/{file_id}.
   * Không dùng trực tiếp làm src ảnh/video vì endpoint này trả JSON { url }.
   */
  getFileUrl: (fileId: string) => {
    return `${axiosInstance.defaults.baseURL}/file/${encodeURIComponent(fileId)}`;
  },
};

export default FileService;

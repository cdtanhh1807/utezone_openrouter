import axiosInstance from "../utils/AxiosInstance";

export const StoryHighlightService = {
  // Lấy danh sách tin nổi bật của một người dùng kèm câu chuyện chi tiết bên trong
  getByUser: (email: string) =>
    axiosInstance.get(`/story_highlight/user/${email}`).then((res) => res.data),

  // Tạo mới một tin nổi bật
  addHighlight: (data: { title: string; coverUrl?: string; storyIds: string[] }) =>
    axiosInstance.post("/story_highlight/add", data).then((res) => res.data),

  // Cập nhật thông tin chủ đề nổi bật
  updateHighlight: (id: string, data: { title?: string; coverUrl?: string; storyIds?: string[] }) =>
    axiosInstance.put(`/story_highlight/update/${id}`, data).then((res) => res.data),

  // Xóa chủ đề tin nổi bật
  deleteHighlight: (id: string) =>
    axiosInstance.delete(`/story_highlight/delete/${id}`).then((res) => res.data),

  // Lấy toàn bộ các story cũ/mới chưa bị xóa (Kho lưu trữ tin) của người dùng hiện tại
  getArchive: () =>
    axiosInstance.get("/story_highlight/archive").then((res) => res.data),
};

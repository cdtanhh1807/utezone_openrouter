import axiosInstance from "../utils/AxiosInstance";

export const announceAPI = {
  getAllAnnounce: () =>
    axiosInstance
      .get("/announce/get_all_announce")
      .then(res => res.data),   
  markAsRead: (announceId: string) =>
    axiosInstance
      .post(`/announce/mark_read/${announceId}`)
      .then(res => res.data),   
};

import axiosInstance from "../utils/AxiosInstance";

export const catalogService = {
    addPostCatalog: (data: any) =>
        axiosInstance
            .post("/post_catalog/add_post_catalog", data)
            .then((res) => res.data),

    updatePostCatalog: (postId: string, data: any) =>
        axiosInstance
            .put(`/post_catalog/update_post_catalog/${postId}`, data)
            .then((res) => res.data),

    findPostCatalog: (postId: string) =>
        axiosInstance
            .post(`/post_catalog/find_post_catalog/${postId}`)
            .then((res) => res.data),

    deletePostCatalog: (postId: string) =>
        axiosInstance
            .delete(`/post_catalog/delete_post_catalog/${postId}`)
            .then((res) => res.data),

    getMyPostCatalog: () =>
        axiosInstance
            .get("/post_catalog/get_my_post_catalog/")
            .then((res) => res.data),

    getPostCatalog: () =>
        axiosInstance
            .get("/post_catalog/get_post_catalog/")
            .then((res) => res.data),
};
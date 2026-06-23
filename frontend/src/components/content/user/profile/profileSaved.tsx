import { useEffect, useRef, useState } from "react";
import "./profileSaved.css";
import { savedAPI } from "../../../../services/SavedService";
import { postAPI } from "../../../../services/PostService";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import MoreHorizOutlinedIcon from "@mui/icons-material/MoreHorizOutlined";
import PostDetail from "../post/postDetail";
import CollectionPrivacyModal from "./CollectionPrivacyModal";
import { jwtDecode } from "jwt-decode";
import AccountService from "../../../../services/AccountService";
import SettingsIcon from "@mui/icons-material/Settings";

interface Post {
  _id: string;
  image: string;
  createdAt: string;
  isVideo?: boolean;
  title?: string;
  content?: string;
  hasMedia?: boolean;
}

interface Collection {
  id: string;
  name: string;
  status?: "public" | "follow" | "private";
  posts: Post[];
}

function ProfileSaved({ email }: { email?: string }) {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [openPostMenu, setOpenPostMenu] = useState<string | null>(null);
  const [activePost, setActivePost] = useState<any>(null);
  const [isPostDetailOpen, setIsPostDetailOpen] = useState(false);
  const [privacyModal, setPrivacyModal] = useState({
    open: false,
    collectionName: "",
    status: "public" as "public" | "follow" | "private",
  });
  const [renameModal, setRenameModal] = useState<{
    open: boolean;
    oldName: string;
    newName: string;
  }>({
    open: false,
    oldName: "",
    newName: "",
  });

  const token = localStorage.getItem("token");
  let currentUserEmail: string | null = null;

  if (!currentUserEmail && token) {
    try {
      interface JwtPayload {
        sub: string;
        role: string;
        exp: number;
        per: string;
      }
      const decoded: JwtPayload = jwtDecode<JwtPayload>(token);
      currentUserEmail = decoded.sub;
    } catch (err) {
      console.error("❌ Token không hợp lệ:", err);
    }
  }

  const fetchCollections = async () => {
    if (!email) return;

    try {
      setLoading(true);

      const res = await savedAPI.getCollections(email);

      const allCollections = res?.post_saved?.collections || [];

      const isOwner = currentUserEmail === email;

      let isFollowing = false;

      const hasFollowCollection = allCollections.some(
        (col: any) => col.status === "follow",
      );

      if (hasFollowCollection && currentUserEmail && !isOwner) {
        try {
          const followRes = await AccountService.check_followed(
            currentUserEmail,
            email,
          );

          console.log(followRes);

          isFollowing = followRes.is_following;
        } catch (err) {
          console.error("check_followed error:", err);
        }
      }

      console.log("Profile owner:", email);
      console.log("Current user:", currentUserEmail);
      console.log("Is owner:", isOwner);
      console.log("Is following:", isFollowing);
      console.log("All collections:", allCollections);

      const rawCollections = allCollections.filter((col: any) => {
        if (col.status === "public") return true;

        if (col.status === "follow") {
          return isOwner || isFollowing;
        }

        if (col.status === "private") {
          return isOwner;
        }

        return false;
      });

      console.log("Visible collections:", rawCollections);

      const mappedCollections: Collection[] = await Promise.all(
        rawCollections.map(async (col: any, index: number) => {
          const posts: Post[] = await Promise.all(
            (col.posts || []).map(async (postId: string) => {
              try {
                const resPost = await postAPI.getById(postId);
                const post = resPost?.post;

                const firstThumbnail = post?.thumbnails?.[0] || "";
                const isVideo = /\.(mp4|mov|avi|webm)$/i.test(firstThumbnail);
                const hasMedia = !!(post?.thumbnails_url?.[0] || post?.image);

                return {
                  _id: postId,
                  image:
                    post?.thumbnails_url?.[0] ||
                    post?.image ||
                    "",
                  createdAt: post?.createdAt || new Date().toISOString(),
                  isVideo,
                  title: post?.title || "",
                  content: post?.content || "",
                  hasMedia,
                };
              } catch {
                return {
                  _id: postId,
                  image: "",
                  createdAt: new Date().toISOString(),
                  isVideo: false,
                  title: "Bài viết không khả dụng",
                  content: "Không thể tải nội dung bài viết này.",
                  hasMedia: false,
                };
              }
            }),
          );

          return {
            id: `${index}`,
            name: col.name,
            status: col.status,
            posts,
          };
        }),
      );

      console.log("Mapped collections:", mappedCollections);

      setCollections(mappedCollections);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCollections();
  }, [email]);

  const menuRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenu(null);
        setOpenPostMenu(null);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // 🗑 XÓA POST KHỎI COLLECTION
  const handleRemovePost = async (collectionName: string, postId: string) => {
    try {
      await savedAPI.removePostFromCollection({
        collection_name: collectionName,
        post_id: postId,
      });

      setCollections((prev) =>
        prev.map((col) =>
          col.name === collectionName
            ? {
                ...col,
                posts: col.posts.filter((p) => p._id !== postId),
              }
            : col,
        ),
      );
    } catch (err) {
      console.error(err);
    }
  };

  const handleOpenPost = async (postId: string) => {
    try {
      const res = await postAPI.getById(postId);
      const post = res.post || res;

      setActivePost(post);
      setIsPostDetailOpen(true);
    } catch (err) {
      console.error("Lỗi mở bài viết", err);
    }
  };

  // 🗑 XÓA COLLECTION
  const handleDeleteCollection = async (collectionName: string) => {
    try {
      await savedAPI.deleteCollection({
        collection_name: collectionName,
      });

      setCollections((prev) => prev.filter((c) => c.name !== collectionName));
    } catch (err) {
      console.error(err);
    }
  };

  // ✏️ RENAME COLLECTION
  const handleRenameCollection = async () => {
    const { oldName, newName } = renameModal;

    if (!newName.trim()) return;

    try {
      await savedAPI.addCollection({
        collection_name: newName,
      });

      const col = collections.find((c) => c.name === oldName);

      if (col) {
        for (const post of col.posts) {
          await savedAPI.addPostToCollection({
            collection_name: newName,
            post_id: post._id,
          });
        }

        await savedAPI.deleteCollection({
          collection_name: oldName,
        });
      }

      setCollections((prev) =>
        prev.map((c) => (c.name === oldName ? { ...c, name: newName } : c)),
      );

      // đóng modal
      setRenameModal({ open: false, oldName: "", newName: "" });
    } catch (err) {
      console.error(err);
    }
  };

  const refreshPost = async (postId: string) => {
    const updated = await postAPI.getById(postId);
    const updatedPost = updated.post || updated;
    setActivePost(updatedPost);
  };

  const openOriginalPost = async (originalPostId: string) => {
    try {
      const res = await postAPI.getById(originalPostId);
      const originalPost = res.post || res;

      setIsPostDetailOpen(false);
      requestAnimationFrame(() => {
        setActivePost(originalPost);
        setIsPostDetailOpen(true);
      });
    } catch (err) {
      console.error("Không lấy được bài viết gốc", err);
    }
  };

  if (loading) return <div>Đang tải bộ sưu tập...</div>;
  if (collections.length === 0) return <div>Chưa có bộ sưu tập nào 📌</div>;

  return (
    <div className="saved-container">
      {collections.map((col) => (
        <div key={col.id} className="collection">
          {/* COLLECTION HEADER */}
          <div className="collection-title-row">
            <h3 className="collection-title">{col.name}</h3>

            <div
              className="dots"
              onClick={() =>
                setOpenMenu(openMenu === col.name ? null : col.name)
              }
            >
              <MoreHorizOutlinedIcon />
              {openMenu === col.name && (
                <div className="menu" ref={menuRef}>
                  <div
                    className="menu-item"
                    onClick={() =>
                      setRenameModal({
                        open: true,
                        oldName: col.name,
                        newName: col.name,
                      })
                    }
                  >
                    <EditIcon /> <span>Đổi tên bộ sưu tập</span>
                  </div>
                  <div
                    className="menu-item"
                    onClick={() =>
                      setPrivacyModal({
                        open: true,
                        collectionName: col.name,
                        status: col.status!,
                      })
                    }
                  >
                    <SettingsIcon />
                    <span>Cài đặt quyền riêng tư</span>
                  </div>

                  <div
                    className="menu-item"
                    onClick={() => handleDeleteCollection(col.name)}
                  >
                    <DeleteIcon /> <span>Xóa bộ sưu tập</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* POSTS */}
          <div className="collection-grid">
            {col.posts.map((post) => (
              <div
                key={post._id}
                className="collection-item"
                onClick={() => handleOpenPost(post._id)}
              >
                <div
                  className="post-dots"
                  onClick={() =>
                    setOpenPostMenu(openPostMenu === post._id ? null : post._id)
                  }
                >
                  <DeleteIcon
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemovePost(col.name, post._id);
                    }}
                  />
                </div>

                {post.isVideo ? (
                  <video src={post.image} muted playsInline autoPlay loop />
                ) : post.hasMedia ? (
                  <img src={post.image} alt="saved" />
                ) : (
                  <div className="no-media-post">
                    <h4 className="no-media-title">{post.title}</h4>
                    <p className="no-media-content">{post.content}</p>
                  </div>
                )}

                <div className="overlay">
                  {new Date(post.createdAt).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {isPostDetailOpen && activePost && (
        <PostDetail
          activePost={activePost}
          onClose={() => setIsPostDetailOpen(false)}
          onCommentAdded={refreshPost}
          onOpenOriginalPost={openOriginalPost}
        />
      )}
      {renameModal.open && (
        <div className="rename-modal-overlay">
          <div className="rename-modal">
            <h3>Đổi tên bộ sưu tập</h3>

            <input
              value={renameModal.newName}
              onChange={(e) =>
                setRenameModal((prev) => ({
                  ...prev,
                  newName: e.target.value,
                }))
              }
              className="rename-input"
              autoFocus
            />

            <div className="rename-actions">
              <button
                onClick={() =>
                  setRenameModal({ open: false, oldName: "", newName: "" })
                }
              >
                Hủy
              </button>

              <button onClick={handleRenameCollection}>Lưu</button>
            </div>
          </div>
        </div>
      )}
      <CollectionPrivacyModal
        open={privacyModal.open}
        value={privacyModal.status}
        onClose={() =>
          setPrivacyModal((prev) => ({
            ...prev,
            open: false,
          }))
        }
        onChange={(status) =>
          setPrivacyModal((prev) => ({
            ...prev,
            status,
          }))
        }
        onSave={async () => {
          await savedAPI.updateStatusCollection({
            collection_name: privacyModal.collectionName,
            status: privacyModal.status,
          });

          fetchCollections();

          setPrivacyModal((prev) => ({
            ...prev,
            open: false,
          }));
        }}
      />
    </div>
  );
}

export default ProfileSaved;

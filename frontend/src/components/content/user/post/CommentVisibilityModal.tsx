import "./CommentVisibilityModal.css";
import PublicIcon from "@mui/icons-material/Public";
import GroupIcon from "@mui/icons-material/Group";
import LockIcon from "@mui/icons-material/Lock";

interface Props {
  open: boolean;
  value: "public" | "follow" | "private";
  onClose: () => void;
  onChange: (value: "public" | "follow" | "private") => void;
  onSave: () => void;
}

export default function CommentVisibilityModal({
  open,
  value,
  onClose,
  onChange,
  onSave,
}: Props) {
  if (!open) return null;

  return (
    <div className="commentVisibilityOverlay" onClick={onClose}>
      <div
        className="commentVisibilityModal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="commentVisibilityHeader">
          <h3>Ai có thể bình luận về bài viết này?</h3>
          <p>Chọn đối tượng được phép bình luận bài viết của bạn.</p>
        </div>

        <div className="commentVisibilityOptions">
          <label className="commentVisibilityOption">
            <input
              type="radio"
              name="commentVisibility"
              checked={value === "public"}
              onChange={() => onChange("public")}
            />

            <div className="optionContent">
              <div className="optionHeader">
                <PublicIcon className="optionIcon" />
                <div className="title">Công khai</div>
              </div>

              <div className="description">
                Mọi người đều có thể bình luận.
              </div>
            </div>
          </label>

          <label className="commentVisibilityOption">
            <input
              type="radio"
              name="commentVisibility"
              checked={value === "follow"}
              onChange={() => onChange("follow")}
            />

            <div className="optionContent">
              <div className="optionHeader">
                <GroupIcon className="optionIcon" />
                <div className="title">Người theo dõi</div>
              </div>

              <div className="description">
                Chỉ người theo dõi bạn mới có thể bình luận.
              </div>
            </div>
          </label>

          <label className="commentVisibilityOption">
            <input
              type="radio"
              name="commentVisibility"
              checked={value === "private"}
              onChange={() => onChange("private")}
            />

            <div className="optionContent">
              <div className="optionHeader">
                <LockIcon className="optionIcon" />
                <div className="title">Chỉ mình tôi</div>
              </div>

              <div className="description">
                Không ai khác có thể bình luận.
              </div>
            </div>
          </label>
        </div>

        <div className="commentVisibilityActions">
          <button className="cancelBtn" onClick={onClose}>
            Hủy
          </button>

          <button className="saveBtn" onClick={onSave}>
            Lưu thay đổi
          </button>
        </div>
      </div>
    </div>
  );
}
import { useState } from "react";
import AccountService from "../../../../services/AccountService";
import type { FollowBlockRequest } from "../../../../services/AccountService";
import RemoveIcon from '@mui/icons-material/Remove';

interface UnFollowButtonProps {
  ownerEmail: string;
  clientEmail: string;
  onUnFollowSuccess?: () => void;
}

export const UnFollowButton = ({ ownerEmail, clientEmail, onUnFollowSuccess }: UnFollowButtonProps) => {
  const [loading, setLoading] = useState(false);

  const handleUnFollow = async () => {
    setLoading(true);

    const data: FollowBlockRequest = { owner: ownerEmail, client: clientEmail };

    try {
      const res = await AccountService.un_follow(data);
      if (res.message) {
        if (onUnFollowSuccess) onUnFollowSuccess();
        window.dispatchEvent(new CustomEvent("relation-changed"));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button className="btn-unfollow" onClick={handleUnFollow} disabled={loading}>
      {!loading && <RemoveIcon fontSize="small" />}
      {loading ? "Đang xử lý..." : "Bỏ theo dõi"}
    </button>
  );
};

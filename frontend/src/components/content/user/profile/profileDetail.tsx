import './profileDetail.css';
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { jwtDecode } from 'jwt-decode';
import AccountService from '../../../../services/AccountService';
import PlaceIcon from '@mui/icons-material/Place';
import GroupIcon from '@mui/icons-material/Group';
import PhoneIcon from '@mui/icons-material/Phone';
import CakeIcon from '@mui/icons-material/Cake';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import RelationshipModal from '../relationship/listRelationship';
import type { UserInfo } from '../../../../types/Account';

import faeLogo from "../../../../assets/avt_department/fae.jpeg";
import fasLogo from "../../../../assets/avt_department/fas.jpg";
import fceLogo from "../../../../assets/avt_department/fce.jpg";
import fcftLogo from "../../../../assets/avt_department/fcft.png";
import feLogo from "../../../../assets/avt_department/fe.png";
import feeeLogo from "../../../../assets/avt_department/feee.png";
import feetLogo from "../../../../assets/avt_department/feet.jpg";
import fflLogo from "../../../../assets/avt_department/ffl.png";
import fgamLogo from "../../../../assets/avt_department/fgam.jpg";
import fitLogo from "../../../../assets/avt_department/fit.png";
import fmeLogo from "../../../../assets/avt_department/fme.jpg";
import fpiLogo from "../../../../assets/avt_department/fpi.png";
import iteLogo from "../../../../assets/avt_department/ite.jpg";
import defaultLogo from "../../../../assets/logo.png";

const logoMap: Record<string, string> = {
  "CƠ KHÍ CHẾ TẠO MÁY": fmeLogo,
  "CÔNG NGHỆ THÔNG TIN": fitLogo,
  "CHÍNH TRỊ LUẬT": feLogo,
  "CHÍNH TRỊ VÀ LUẬT": feLogo,
  "ĐIỆN - ĐIỆN TỬ": feeeLogo,
  "CÔNG NGHỆ HÓA HỌC VÀ THỰC PHẨM": fcftLogo,
  "IN VÀ TRUYỀN THÔNG": fpiLogo,
  "KHOA HỌC ỨNG DỤNG": fasLogo,
  "KINH TẾ": feetLogo,
  "NGOẠI NGỮ": fflLogo,
  "THỜI TRANG VÀ DU LỊCH": fgamLogo,
  "VIỆN SƯ PHẠM KỸ THUẬT": iteLogo,
  "XÂY DỰNG": fceLogo,
  "CƠ KHÍ ĐỘNG LỰC": faeLogo,
};

const formatDate = (dateStr?: string) => {
  if (!dateStr) return "Chưa cập nhật";
  const parts = dateStr.split("T")[0].split("-");
  if (parts.length === 3) {
    const [year, month, day] = parts;
    return `${day}/${month}/${year}`;
  }
  return dateStr;
};

interface FollowedUser {
  email: string;
  fullName: string;
  avatar: string;
}

interface DecodedToken {
  sub: string;
  role?: string;
  exp?: number;
  per?: string;
}

interface ProfileDetailProps {
  email?: string;
}

const ProfileDetail = ({ email }: ProfileDetailProps) => {
  const [profileUser, setProfileUser] = useState<UserInfo | null>(null);
  const [followedDetails, setFollowedDetails] = useState<FollowedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRelationOpen, setIsRelationOpen] = useState(false);
  const navigate = useNavigate();

  const token = localStorage.getItem("token");
  let decodedEmail: string | null = null;
  if (token) {
    try {
      const decoded = jwtDecode<DecodedToken>(token);
      decodedEmail = decoded.sub;
    } catch (err) {
      console.error("❌ Token không hợp lệ:", err);
    }
  }
  const targetEmail = email;

  useEffect(() => {
    if (!targetEmail) return;

    const fetchProfileData = async () => {
      setLoading(true);
      try {
        const data = await AccountService.get_account_info(targetEmail);
        setProfileUser(data);

        const followedEmails = data.followed || [];
        if (followedEmails.length > 0) {
          // Lấy tối đa 9 email ngẫu nhiên nếu nhiều hơn 9
          let selectedEmails = [...followedEmails];
          if (selectedEmails.length > 9) {
            selectedEmails = selectedEmails.sort(() => 0.5 - Math.random()).slice(0, 9);
          }

          const details = await Promise.all(
            selectedEmails.map(async (fEmail: string) => {
              try {
                const fInfo = await AccountService.get_account_info(fEmail);
                return {
                  email: fEmail,
                  fullName: fInfo.fullName || fEmail,
                  avatar: fInfo.avatar || "/default-avatar.png",
                };
              } catch (e) {
                console.error(`❌ Lỗi tải thông tin của ${fEmail}:`, e);
                return {
                  email: fEmail,
                  fullName: fEmail,
                  avatar: "/default-avatar.png",
                };
              }
            })
          );
          setFollowedDetails(details);
        } else {
          setFollowedDetails([]);
        }
      } catch (err) {
        console.error("❌ Lỗi gọi API trong ProfileDetail:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchProfileData();
  }, [targetEmail]);

  return (
    <div className="profile-sidebar-container">
      <div className="profileDetail-modern-card">
        <h3 className="detail-card-title">Giới thiệu</h3>
        
        {/* Hình ảnh/Logo khoa */}
        {profileUser?.role !== "Moderator" && (
          <div className="detail-header-visual">
            <div className="faculty-logo-wrapper">
              <img
                className="faculty-logo"
                src={logoMap[profileUser?.department?.toUpperCase() || ""] || defaultLogo}
                alt="faculty-avatar"
              />
            </div>
          </div>
        )}

        {/* Danh sách thông tin */}
        <div className="detail-info-list">
          {/* Khoa/Phòng ban (Dữ liệu động từ API) */}
          {profileUser?.role !== "Moderator" && (
            <div className="detail-item-row">
              <GroupIcon className="detail-icon" />
              <span className="detail-text">
                Khoa: <strong>{profileUser?.department || 'CÔNG NGHỆ THÔNG TIN'}</strong>
              </span>
            </div>
          )}
          
          {/* Địa chỉ (Dữ liệu động từ API) */}
          <div className="detail-item-row">
            <PlaceIcon className="detail-icon" />
            <span className="detail-text">
              {profileUser?.role === "Moderator" ? "Địa chỉ: " : "Sống tại: "}
              <strong>{profileUser?.address || "Chưa cập nhật"}</strong>
            </span>
          </div>

          {/* Số điện thoại (Dữ liệu động từ API) */}
          <div className="detail-item-row">
            <PhoneIcon className="detail-icon" />
            <span className="detail-text">Số điện thoại: <strong>{profileUser?.phone || "Chưa cập nhật"}</strong></span>
          </div>

          {/* Ngày sinh (Dữ liệu động từ API) */}
          <div className="detail-item-row">
            <CakeIcon className="detail-icon" />
            <span className="detail-text">
              {profileUser?.role === "Moderator" ? "Ngày thành lập: " : "Ngày sinh: "}
              <strong>{formatDate(profileUser?.day_of_birth)}</strong>
            </span>
          </div>
          

        </div>
      </div>

      {/* Danh sách người theo dõi (Followed Grid - Tối đa 9 ô) */}
      <div className="profile-followed-card">
        <div className="followed-card-header">
          <div className="followed-title-container">
            <h3 className="followed-card-title">Đang theo dõi</h3>
            <button className="followed-arrow-btn" onClick={() => setIsRelationOpen(true)}>
              <KeyboardArrowDownIcon />
            </button>
          </div>
          <span className="followed-card-count">
            {profileUser?.followed?.length || 0} người
          </span>
        </div>
        
        {loading ? (
          <div className="followed-loading">Đang tải dữ liệu...</div>
        ) : followedDetails.length > 0 ? (
          <div className="followed-grid">
            {followedDetails.map((item) => (
              <div 
                key={item.email} 
                className="followed-grid-item"
                onClick={() => navigate(`/profile/${item.email}`)}
              >
                <img 
                  src={item.avatar} 
                  alt={item.fullName} 
                  className="followed-item-avatar" 
                />
                <span className="followed-item-name" title={item.fullName}>
                  {item.fullName}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="followed-empty">Chưa theo dõi ai</div>
        )}
      </div>

      {isRelationOpen && decodedEmail && targetEmail && (
        <RelationshipModal
          isOpen={isRelationOpen}
          onClose={() => setIsRelationOpen(false)}
          profileEmail={targetEmail}
          myEmail={decodedEmail}
          initialTab={1}
        />
      )}
    </div>
  );
};

export default ProfileDetail;
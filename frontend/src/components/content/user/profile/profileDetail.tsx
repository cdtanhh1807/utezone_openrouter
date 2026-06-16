import './profileDetail.css';
import WorkIcon from '@mui/icons-material/Work';
import PlaceIcon from '@mui/icons-material/Place';
import GroupIcon from '@mui/icons-material/Group';
import AccessTimeIcon from '@mui/icons-material/AccessTime';

const ProfileDetail = () => {
    return (
        <div className="profileDetail-modern-card">
            
            {/* Hình ảnh/Logo (được thu nhỏ và bo góc tròn đặt giữa tinh tế) */}
            <div className="detail-header-visual">
                <div className="faculty-logo-wrapper">
                    <img
                        className="faculty-logo"
                        src="https://fit.hcmute.edu.vn/Resources/Images/SubDomain/fit/logo-cntt2021.png"
                        alt="faculty-avatar"
                    />
                </div>
            </div>

            {/* Danh sách thông tin */}
            <div className="detail-info-list">
                <div className="detail-item-row">
                    <WorkIcon className="detail-icon" />
                    <span className="detail-text">Đã tốt nghiệp <strong>HCMUTE</strong> ngành Công Nghệ thông Tin</span>
                </div>
                
                <div className="detail-item-row">
                    <PlaceIcon className="detail-icon" />
                    <span className="detail-text">Sống tại <strong>Thành phố Hồ Chí Minh</strong></span>
                </div>
                
                <div className="detail-item-row">
                    <GroupIcon className="detail-icon" />
                    <span className="detail-text">Là thành viên khoa <strong>Công Nghệ thông Tin</strong></span>
                </div>
                
                <div className="detail-item-row">
                    <AccessTimeIcon className="detail-icon" />
                    <span className="detail-text">Tuổi UTEzone: <strong>2 năm</strong></span>
                </div>
            </div>
        </div>
    );
}

export default ProfileDetail;
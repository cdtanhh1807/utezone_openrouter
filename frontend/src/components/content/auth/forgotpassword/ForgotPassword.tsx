import { useState, type ChangeEvent, type FormEvent, useEffect } from 'react';
import axiosInstance from '../../../../utils/AxiosInstance';
import { Link, useNavigate } from 'react-router-dom';
import logo from "../../../../assets/logo.png";
import './ForgotPassword.css';

type ForgotPasswordForm = {
    email: string;
    otp: string;
    newPassword: string;
};

function ForgotPassword() {
    const [formData, setFormData] = useState<ForgotPasswordForm>({
        email: '',
        otp: '',
        newPassword: ''
    });
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const navigate = useNavigate();

    useEffect(() => {
        document.body.classList.add("login-page");
        return () => {
            document.body.classList.remove("login-page");
        };
    }, []);

    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            // Gửi đúng payload với otp và newPassword rỗng (theo file cũ)
            await axiosInstance.post('/account/forgot-password', {
                email: formData.email,
                otp: formData.otp,
                new_password: formData.newPassword
            });
            // Sau khi gửi email thành công, chuyển sang trang nhập OTP
            navigate('/verify-forgot-password', { state: { email: formData.email } });
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Không thể gửi yêu cầu, vui lòng thử lại');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-logo">
                    <img src={logo} alt="Logo" className="logo-img" />
                </div>

                <div className="slogan" style={{ fontSize: '22px', marginBottom: '20px' }}>
                    <span className="slogan-blue">Quên mật khẩu</span>
                </div>

                <form onSubmit={handleSubmit}>
                    <input
                        type="email"
                        name="email"
                        placeholder="Nhập email của bạn"
                        value={formData.email}
                        onChange={handleChange}
                        required
                    />
                    {/* Ẩn hai trường otp và newPassword nhưng vẫn giữ trong state */}
                    <input type="hidden" name="otp" value={formData.otp} />
                    <input type="hidden" name="newPassword" value={formData.newPassword} />
                    <button type="submit" disabled={isLoading} className="signin-btn">
                        {isLoading ? 'Đang gửi...' : 'Gửi OTP'}
                    </button>
                    {error && <div className="error-message">{error}</div>}
                </form>

                <div className="create-account" style={{ marginTop: '10px' }}>
                    <Link to="/login">Quay lại đăng nhập</Link>
                </div>

                <div className="terms">
                    Copyright © 2026 utezone.site | Powered by utezone.site
                </div>
            </div>
        </div>
    );
}

export default ForgotPassword;
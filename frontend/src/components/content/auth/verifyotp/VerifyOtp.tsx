import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { useState, type FormEvent, useEffect } from "react";
import axiosInstance from "../../../../utils/AxiosInstance";
import { isTokenExpired } from '../../../../utils/Auth';
import logo from "../../../../assets/logo.png";
import './VerifyOtp.css';
import { Link } from "react-router-dom";

function VerifyOtp() {
    const token = localStorage.getItem('token');
    if (token && !isTokenExpired(token)) {
        return <Navigate to="/" replace />;
    }

    const location = useLocation();
    const navigate = useNavigate();
    const email = (location.state as { email: string })?.email;

    const [otp, setOtp] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        document.body.classList.add("login-page");
        return () => {
            document.body.classList.remove("login-page");
        };
    }, []);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            const response = await axiosInstance.post<{ message: string }>(
                "/account/verify-otp/",
                { email, otp }
            );
            console.log(response.data.message);
            navigate("/login");
        } catch (err: any) {
            const msg = err.response?.data?.message || "OTP không đúng hoặc đã hết hạn.";
            setError(msg);
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

                <div className="slogan" style={{ fontSize: '22px', marginBottom: '10px' }}>
                    <span className="slogan-blue">Xác minh OTP</span>
                </div>
                <p style={{ textAlign: 'center', color: '#555', marginBottom: '20px', fontSize: '14px' }}>
                    Chúng tôi đã gửi mã OTP tới email: <b>{email}</b>
                </p>

                <form onSubmit={handleSubmit}>
                    <input
                        type="text"
                        placeholder="Nhập OTP"
                        value={otp}
                        onChange={e => setOtp(e.target.value)}
                        required
                    />
                    <button type="submit" disabled={isLoading} className="signin-btn">
                        {isLoading ? "Đang xác minh..." : "Xác minh"}
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

export default VerifyOtp;
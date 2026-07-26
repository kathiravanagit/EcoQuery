import React from 'react';
import { useNavigate } from 'react-router-dom';
import { User } from 'lucide-react';
import './ProfileMenu.css';

const ProfileMenu = () => {
  const navigate = useNavigate();

  return (
    <button
      className="profile-icon-btn"
      onClick={() => navigate('/profile')}
      aria-label="Profile"
    >
      <User size={20} />
    </button>
  );
};

export default ProfileMenu;

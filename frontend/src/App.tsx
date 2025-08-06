import React from 'react';
import { ConfigProvider } from 'antd';
import koKR from 'antd/locale/ko_KR';
import { Dashboard } from './components/Dashboard/Dashboard';
import 'antd/dist/reset.css';
import './App.css';

function App() {
  return (
    <ConfigProvider locale={koKR}>
      <Dashboard />
    </ConfigProvider>
  );
}

export default App;

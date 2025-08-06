import React from 'react';
import { Select, DatePicker, Space, Button, Slider, Typography } from 'antd';
import { ThunderboltOutlined, CalendarOutlined, ClockCircleOutlined } from '@ant-design/icons';
import moment, { Moment } from 'moment';
import { TimeSelection } from '../../types';

const { Text } = Typography;

const { Option } = Select;

interface TimeSelectorProps {
  selectedTime: TimeSelection;
  onChange: (timeSelection: TimeSelection) => void;
  loading?: boolean;
  onPredict?: () => void;
}

export const TimeSelector: React.FC<TimeSelectorProps> = ({
  selectedTime,
  onChange,
  loading = false,
  onPredict,
}) => {
  // 24시간 옵션 생성
  const hourOptions = Array.from({ length: 24 }, (_, i) => ({
    value: i,
    label: `${String(i).padStart(2, '0')}:00`,
  }));

  const handleDateChange = (date: Moment | null, dateString: string | string[]) => {
    if (date && typeof dateString === 'string') {
      onChange({
        ...selectedTime,
        date: dateString,
      });
    }
  };

  const handleHourChange = (hour: number) => {
    onChange({
      ...selectedTime,
      hour,
    });
  };

  // 시간대 레이블 생성
  const getTimeLabel = (hour: number) => {
    if (hour >= 0 && hour < 6) return '심야';
    if (hour >= 6 && hour < 10) return '오전 피크';
    if (hour >= 10 && hour < 17) return '주간';
    if (hour >= 17 && hour < 20) return '저녁 피크';
    return '저녁';
  };

  return (
    <div style={{ 
      background: '#fff', 
      padding: '20px', 
      borderRadius: '12px',
      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
      marginBottom: '16px',
      border: '1px solid #f0f0f0'
    }}>
      <h3 style={{ 
        margin: '0 0 12px 0', 
        fontSize: '16px', 
        fontWeight: 'bold',
        color: '#1890ff'
      }}>
        예측 시점 선택
      </h3>
      
      <Space size="middle" wrap>
        <div>
          <label style={{ 
            display: 'block', 
            marginBottom: '4px', 
            fontSize: '12px',
            fontWeight: 'bold',
            color: '#666'
          }}>
            날짜
          </label>
          <DatePicker
            value={selectedTime.date ? moment(selectedTime.date) : null}
            onChange={handleDateChange}
            format="YYYY-MM-DD"
            placeholder="날짜 선택"
            style={{ width: 140 }}
            disabled={loading}
            disabledDate={(current) => {
              if (!current) return false;
              // 2024-11-01 ~ 2025-06-25 범위 제한
              const minDate = moment('2024-11-01');
              const maxDate = moment('2025-06-25');
              return current < minDate || current > maxDate;
            }}
          />
        </div>

        <div>
          <label style={{ 
            display: 'block', 
            marginBottom: '4px', 
            fontSize: '12px',
            fontWeight: 'bold',
            color: '#666'
          }}>
            시간
          </label>
          <Select
            value={selectedTime.hour}
            onChange={handleHourChange}
            style={{ width: 100 }}
            disabled={loading}
            placeholder="시간"
          >
            {hourOptions.map(option => (
              <Option key={option.value} value={option.value}>
                {option.label}
              </Option>
            ))}
          </Select>
        </div>

        <div style={{ paddingTop: '18px' }}>
          <div style={{
            fontSize: '11px',
            color: '#999',
            lineHeight: '1.2'
          }}>
            <div>• 다음 24시간 DRT 수요 예측</div>
            <div>• 2024-11-01 ~ 2025-06-25 범위</div>
          </div>
        </div>
      </Space>

      {selectedTime.date && selectedTime.hour !== undefined && (
        <div style={{
          marginTop: '12px',
          padding: '8px 12px',
          background: '#f6ffed',
          border: '1px solid #b7eb8f',
          borderRadius: '4px',
          fontSize: '12px'
        }}>
          <strong>선택된 예측 시점:</strong> {selectedTime.date} {String(selectedTime.hour).padStart(2, '0')}:00
        </div>
      )}

      {/* 예측 버튼 */}
      <div style={{ marginTop: '16px' }}>
        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={onPredict}
          loading={loading}
          disabled={!selectedTime.date || selectedTime.hour === undefined}
          block
          size="large"
          style={{
            background: '#52c41a',
            borderColor: '#52c41a',
            fontWeight: 'bold'
          }}
        >
          {loading ? 'DRT 수요 예측 중...' : 'DRT 수요 예측하기'}
        </Button>
      </div>
    </div>
  );
};


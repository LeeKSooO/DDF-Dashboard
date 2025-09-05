"use client";
import { memo, useMemo } from "react";
import { ResponsiveContainer, BarChart, Bar } from "recharts";

type Props = { fill: string };

function SparkBarImpl({ fill }: Props) {
  // 절대 새로운 배열 만들지 말고 useMemo로 고정
  const data = useMemo(() => ([
    { value: 10 }, { value: 15 }, { value: 12 }, { value: 18 }
  ]), []);

  return (
    <div className="w-16 h-12 opacity-60">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <Bar dataKey="value" fill={fill} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export const SparkBar = memo(SparkBarImpl);
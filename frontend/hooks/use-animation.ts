import { useState, useCallback, useRef } from "react";

export interface AnimationControls {
  animatedNumbers: Record<string, number>;
  animateNumber: (key: string, targetValue: number, duration?: number) => void;
  resetAnimations: () => void;
  isAnimationComplete: (key: string, targetValue: number) => boolean;
}

export const useAnimation = (): AnimationControls => {
  const [animatedNumbers, setAnimatedNumbers] = useState<Record<string, number>>({});
  const animationRefs = useRef<Record<string, boolean>>({});

  const animateNumber = useCallback((key: string, targetValue: number, duration: number = 1500) => {
    // 이미 애니메이션이 진행 중이거나 완료된 경우 건너뛰기
    if (animatedNumbers[key] === targetValue || animationRefs.current[key]) {
      return;
    }

    animationRefs.current[key] = true;
    
    const startValue = 0;
    const startTime = Date.now();
    
    const easeOutCubic = (t: number): number => {
      return 1 - Math.pow(1 - t, 3);
    };
    
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeProgress = easeOutCubic(progress);
      const currentValue = Math.floor(startValue + (targetValue - startValue) * easeProgress);
      
      setAnimatedNumbers(prev => ({
        ...prev,
        [key]: currentValue
      }));
      
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        // 완료 시 정확한 목표값으로 설정
        setAnimatedNumbers(prev => ({
          ...prev,
          [key]: targetValue
        }));
        animationRefs.current[key] = false;
      }
    };
    
    requestAnimationFrame(animate);
  }, [animatedNumbers]);

  const resetAnimations = useCallback(() => {
    setAnimatedNumbers({});
    animationRefs.current = {};
  }, []);

  const isAnimationComplete = useCallback((key: string, targetValue: number) => {
    return animatedNumbers[key] === targetValue;
  }, [animatedNumbers]);

  return {
    animatedNumbers,
    animateNumber,
    resetAnimations,
    isAnimationComplete
  };
};
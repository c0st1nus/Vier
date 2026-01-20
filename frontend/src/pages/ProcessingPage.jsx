// Processing Page - Real-time progress tracking
import React, { useEffect, useState } from 'react';
import './ProcessingPage.css';

const ProcessingPage = ({ taskId, status, progress, currentStage, uploadProgress }) => {
    const [dots, setDots] = useState('');

    // Animated dots for loading text
    useEffect(() => {
        const interval = setInterval(() => {
            setDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
        }, 500);
        return () => clearInterval(interval);
    }, []);

    // Get stage information
    const getStageInfo = () => {
        const stages = {
            'downloading': {
                icon: (
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                ),
                title: 'Downloading Video',
                description: 'Fetching video content from the source',
            },
            'extracting_audio': {
                icon: (
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                ),
                title: 'Extracting Audio',
                description: 'Converting video audio for processing',
            },
            'transcribing': {
                icon: (
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                ),
                title: 'Transcribing Audio',
                description: 'Converting speech to text using AI',
            },
            'analyzing_frames': {
                icon: (
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                ),
                title: 'Analyzing Frames',
                description: 'Extracting visual information from video',
            },
            'generating_quizzes': {
                icon: (
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                ),
                title: 'Generating Quizzes',
                description: 'Creating interactive quiz questions with AI',
            },
            'finalizing': {
                icon: (
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                    </svg>
                ),
                title: 'Finalizing',
                description: 'Preparing your results',
            },
        };

        return stages[currentStage] || {
            icon: (
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            ),
            title: 'Processing',
            description: 'Working on your video',
        };
    };

    const stageInfo = getStageInfo();
    const displayProgress = status === 'uploading' ? uploadProgress : progress;

    return (
        <div className="processing-page">
            <div className="container container-sm">
                <div className="processing-container">
                    {/* Progress Circle */}
                    <div className="progress-circle-container">
                        <svg className="progress-circle" width="200" height="200" viewBox="0 0 200 200">
                            <circle
                                className="progress-circle-bg"
                                cx="100"
                                cy="100"
                                r="90"
                                fill="none"
                                strokeWidth="12"
                            />
                            <circle
                                className="progress-circle-fill"
                                cx="100"
                                cy="100"
                                r="90"
                                fill="none"
                                strokeWidth="12"
                                strokeDasharray={`${2 * Math.PI * 90}`}
                                strokeDashoffset={`${2 * Math.PI * 90 * (1 - displayProgress / 100)}`}
                                strokeLinecap="round"
                            />
                        </svg>
                        <div className="progress-content">
                            <div className="progress-icon">
                                {stageInfo.icon}
                            </div>
                            <div className="progress-percentage">{Math.round(displayProgress)}%</div>
                        </div>
                    </div>

                    {/* Status Information */}
                    <div className="status-info">
                        <h2 className="status-title">
                            {status === 'uploading' ? 'Uploading Video' : stageInfo.title}
                            <span className="dots">{dots}</span>
                        </h2>
                        <p className="status-description">
                            {status === 'uploading'
                                ? 'Please wait while we upload your video to our servers'
                                : stageInfo.description}
                        </p>
                    </div>

                    {/* Progress Bar */}
                    <div className="progress-bar-container">
                        <div className="progress-bar">
                            <div
                                className="progress-bar-fill"
                                style={{ width: `${displayProgress}%` }}
                            ></div>
                        </div>
                        <div className="progress-text">
                            <span className="progress-label">
                                {currentStage ? currentStage.replace(/_/g, ' ').toUpperCase() : 'PROCESSING'}
                            </span>
                            <span className="progress-value">{Math.round(displayProgress)}%</span>
                        </div>
                    </div>

                    {/* Task ID */}
                    <div className="task-info">
                        <div className="task-id-container">
                            <span className="task-id-label">Task ID:</span>
                            <code className="task-id">{taskId}</code>
                        </div>
                        <p className="task-hint">
                            Save this ID to check your results later
                        </p>
                    </div>

                    {/* Processing Steps */}
                    <div className="processing-steps">
                        <div className={`step ${['downloading', 'extracting_audio', 'transcribing', 'analyzing_frames', 'generating_quizzes', 'finalizing'].includes(currentStage) ? 'active' : ''} ${progress > 10 ? 'completed' : ''}`}>
                            <div className="step-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                            </div>
                            <span className="step-label">Download</span>
                        </div>

                        <div className="step-divider"></div>

                        <div className={`step ${['transcribing', 'analyzing_frames', 'generating_quizzes', 'finalizing'].includes(currentStage) ? 'active' : ''} ${progress > 30 ? 'completed' : ''}`}>
                            <div className="step-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                                </svg>
                            </div>
                            <span className="step-label">Transcribe</span>
                        </div>

                        <div className="step-divider"></div>

                        <div className={`step ${['analyzing_frames', 'generating_quizzes', 'finalizing'].includes(currentStage) ? 'active' : ''} ${progress > 60 ? 'completed' : ''}`}>
                            <div className="step-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                </svg>
                            </div>
                            <span className="step-label">Analyze</span>
                        </div>

                        <div className="step-divider"></div>

                        <div className={`step ${['generating_quizzes', 'finalizing'].includes(currentStage) ? 'active' : ''} ${progress > 85 ? 'completed' : ''}`}>
                            <div className="step-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                </svg>
                            </div>
                            <span className="step-label">Generate Quiz</span>
                        </div>
                    </div>

                    {/* Info Message */}
                    <div className="processing-info">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <p>
                            This process may take a few minutes depending on video length.
                            Please don't close this window.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ProcessingPage;

# 🚀 TODO: Browser Extension Implementation

## ✅ Completed
- [x] Database migration to new Video-centric architecture
- [x] Authentication system (JWT, registration, login, refresh)
- [x] Video endpoints (upload/url, check, status, segments)
- [x] Database models (User, Video, Segment, Quiz, UserAnswer)
- [x] Auth schemas and services

---

## 📋 Phase 1: Complete Backend Endpoints [ X ]

### 1.1 Quiz Endpoints
**File:** `app/api/endpoints/quiz.py`

**Endpoints to create:**
- `POST /api/quiz/{quiz_id}/answer` - Submit answer to a quiz question
  - Accept `selected_index` in body
  - Validate user is authenticated
  - Check if user already answered (prevent duplicates or allow retake)
  - Calculate if answer is correct
  - Save to `user_answers` table
  - Return `is_correct`, `correct_index`, updated user stats
  
- `GET /api/segment/{segment_id}/status` - Get answer status for segment
  - Return total questions, answered questions, correct answers
  - Return `is_complete` boolean
  - Return score percentage

- `GET /api/segment/{segment_id}/review` - Review answered quizzes
  - Return all quizzes with user's answers
  - Include correct answers and user's selections
  - Include `answered_at` timestamps

- `POST /api/segment/{segment_id}/retake` - Retake segment quizzes
  - Delete existing user answers for this segment
  - Return success message

**Schema file:** `app/schemas/quiz.py` (already created, review and adjust)

---

### 1.2 User Statistics Endpoints
**File:** `app/api/endpoints/user.py`

**Endpoints to create:**
- `GET /api/user/profile` - Get user profile with stats
  - Videos watched count
  - Total questions answered
  - Correct answers count
  - Overall accuracy percentage
  - Current streak (days in a row)

- `GET /api/user/stats` - Detailed statistics
  - Total videos watched
  - Questions answered
  - Accuracy by topic/keyword
  - Recent activity

- `GET /api/user/history` - Video watch history
  - List of all videos user has interacted with
  - For each video: title, watched_at, questions answered, score
  - Pagination support

- `GET /api/user/topics` - Top topics/keywords
  - Most answered topics
  - Accuracy per topic
  - Aggregated from segments' keywords

**Services needed:**
- Create `app/services/user_stats_service.py` for computing statistics
- Implement caching for expensive queries (Redis)

---

### 1.3 WebSocket Endpoint
**File:** `app/api/endpoints/websocket.py`

**Endpoint:**
- `WS /api/video/ws/{task_id}` - Real-time updates for video processing

**Events to send:**
- `connected` - When WebSocket connects
- `segment_ready` - When a segment is processed (includes full segment with quizzes)
- `progress` - Progress updates (percentage, current_stage)
- `completed` - When all segments are done
- `error` - If processing fails

**Authentication:**
- Accept `?token=<jwt>` query parameter
- Validate JWT token
- Optional: allow anonymous connections for public videos

**Connection management:**
- Store active connections in memory or Redis
- Clean up on disconnect
- Handle reconnection logic

---

## 📋 Phase 2: Update Video Processing Pipeline

### 2.1 Refactor Pipeline Service
**File:** `app/services/pipeline.py`

**Changes needed:**
- Replace all references to old `Task` model with `Video` model
- Save segments to database **as they are processed** (not at the end)
- Create `Segment` records with `segment_id`, `start_time`, `end_time`, etc.
- Create `Quiz` records for each question in the segment
- Update `Video.status`, `Video.progress`, `Video.current_stage` in real-time
- Send WebSocket events when segments are ready

**Key functions to update:**
- `process_video_from_url()` - Main entry point
- `segment_and_generate_quizzes()` - Save to DB after each segment
- Status update callbacks - Send WebSocket events

**Database transactions:**
- Each segment should be saved in its own transaction
- If segment processing fails, don't block other segments
- Update video status atomically

---

### 2.2 Background Task Queue
**Current:** Pipeline runs synchronously (blocks request)
**Goal:** Process videos in background

**Options:**
- **Option A (Simple):** Use FastAPI `BackgroundTasks`
  - Easy to implement
  - No external dependencies
  - Limited to single server instance
  
- **Option B (Production):** Use Celery + Redis
  - Distributed task queue
  - Can scale to multiple workers
  - Retry logic and monitoring
  - Requires Redis setup

**Recommendation:** Start with Option A, migrate to Option B later

**Implementation:**
- In `POST /api/video/upload/url`, add background task:
  ```
  background_tasks.add_task(process_video_task, video_id=new_video.id)
  ```
- Create `process_video_task()` function that:
  - Loads video from DB
  - Calls updated pipeline
  - Handles errors and updates status

---

### 2.3 WebSocket Integration in Pipeline
**File:** `app/services/websocket_manager.py`

**Create WebSocket manager:**
- Class to manage all active WebSocket connections
- Methods: `connect()`, `disconnect()`, `send_to_task(task_id, message)`
- Store connections in dictionary: `{task_id: [connection1, connection2, ...]}`

**Integration points in pipeline:**
- After each segment is processed → `websocket_manager.send_to_task(task_id, segment_ready_event)`
- On progress updates → `websocket_manager.send_to_task(task_id, progress_event)`
- On completion → `websocket_manager.send_to_task(task_id, completed_event)`
- On error → `websocket_manager.send_to_task(task_id, error_event)`

---

### 2.4 Video Caching Strategy
**Current:** Check if video exists by URL + language
**Issue:** Same video URL might be processed multiple times if ongoing

**Solution:**
- Lock mechanism during processing (Redis lock or DB flag)
- If video is `PROCESSING`, subsequent requests should:
  - Return existing task_id
  - Connect to same WebSocket
  - Not start new processing

**Implementation:**
- Add `processing_lock` field or use Redis distributed lock
- Check lock before starting new processing
- Release lock on completion or failure

---

## 📋 Phase 3: Browser Extension

### 3.1 Extension Structure
**Manifest V3** (Chrome + Firefox compatible)

**Files to create:**
- `extension/manifest.json` - Extension metadata and permissions
- `extension/background.js` - Service worker (API calls, WebSocket)
- `extension/content.js` - Injected into YouTube pages (video detection, overlay)
- `extension/sidepanel.html` - Side panel UI (auth, stats, segments)
- `extension/sidepanel.js` - Side panel logic
- `extension/overlay.html` - Quiz overlay template
- `extension/overlay.css` - Overlay styles
- `extension/icons/` - Extension icons (16x16, 48x48, 128x128)

**Permissions needed:**
- `storage` - Save tokens and settings
- `activeTab` - Access current tab
- `sidePanel` - Chrome side panel API
- `webRequest` (optional) - Intercept video URLs
- Host permissions: `*://*.youtube.com/*`, `*://16.171.11.38:2135/*` (backend)

---

### 3.2 Side Panel Features
**File:** `extension/sidepanel.html` + `extension/sidepanel.js`

**Sections:**
1. **Auth Section** (if not logged in)
   - Login form (email, password)
   - Register link
   - Store tokens in `chrome.storage.local`

2. **User Info** (if logged in)
   - Email
   - Logout button
   - Quick stats (videos watched, accuracy)

3. **Settings**
   - Language selection (en/ru/kk)
   - Auto-detect from browser: `chrome.i18n.getUILanguage()`
   - Enable/disable extension toggle

4. **Current Video Section**
   - Video title
   - Processing status (pending/processing/completed)
   - Progress bar

5. **Segments List**
   - List all segments for current video
   - Show status: ✅ ready, ⏳ processing, 🔒 not ready
   - Show answered status: "3/5 questions answered"
   - Click to open overlay with quizzes

**Communication:**
- `sidepanel.js` sends messages to `background.js`
- `background.js` responds with data from API/WebSocket
- Use `chrome.runtime.sendMessage()` and `chrome.runtime.onMessage`

---

### 3.3 Content Script (Video Detection)
**File:** `extension/content.js`

**Tasks:**
1. **Detect video player**
   - Check for `<video>` element on page
   - For YouTube: `document.querySelector('video')`
   - Store reference to video element

2. **Listen to video events**
   - `play` → Send video URL to background for processing
   - `timeupdate` → Check if reached segment end (-10 seconds)
   - `pause`, `ended` → Handle appropriately

3. **Inject floating quiz button** 🎓
   - Create button element with badge (question count)
   - Position: fixed, bottom-right corner of video
   - Show when: segment end time ± 3 seconds
   - Animation: fade in/out smoothly
   - Click → Show quiz overlay

4. **Inject quiz overlay**
   - Create modal overlay (full-screen or centered)
   - Load `overlay.html` template
   - Insert into page DOM (use Shadow DOM to avoid style conflicts)
   - Pause video when overlay appears (optional based on settings)
   - Resume video when overlay closes

**Communication:**
- Send messages to `background.js` when video starts
- Receive segment data from `background.js`
- Update UI based on segment status

---

### 3.4 Background Service Worker
**File:** `extension/background.js`

**Responsibilities:**
1. **API Communication**
   - Store backend URL (configurable, default: `http://16.171.11.38:2135`)
   - Store JWT tokens in `chrome.storage.local`
   - Methods: `login()`, `register()`, `refreshToken()`, `logout()`
   - Methods: `checkVideo()`, `uploadVideo()`, `getSegments()`, `submitAnswer()`
   - Handle 401 errors → refresh token automatically

2. **WebSocket Connection**
   - Open WebSocket when video processing starts
   - Parse incoming events (`segment_ready`, `progress`, `completed`, `error`)
   - Store segment data in memory
   - Send updates to `sidepanel.js` and `content.js`
   - Reconnect on disconnect

3. **State Management**
   - Current video URL and task_id
   - All segments for current video
   - User's answer status for each quiz
   - Active tab tracking (which tab has video playing)

4. **Message Handling**
   - Listen to messages from `content.js` and `sidepanel.js`
   - Route messages appropriately
   - Respond with requested data

**Storage structure:**
```
chrome.storage.local:
{
  "access_token": "...",
  "refresh_token": "...",
  "user": {...},
  "language": "en",
  "enabled": true,
  "backend_url": "http://16.171.11.38:2135"
}
```

---

### 3.5 Quiz Overlay UI
**File:** `extension/overlay.html` + `extension/overlay.css`

**Features:**
1. **Pagination** (one question per screen)
   - Question number: "Question 1 of 5"
   - Progress dots or bar
   - Next/Previous buttons

2. **Question Display**
   - Question text
   - Multiple choice options (A, B, C, D)
   - Radio buttons or clickable cards
   - "Check Answer" button (enabled after selection)

3. **Answer Feedback**
   - After clicking "Check Answer":
     - Highlight correct answer in green
     - If wrong, highlight user's answer in red
     - Show "✅ Correct!" or "❌ Incorrect"
     - Show explanation (if available in future)
   - "Next Question" button appears

4. **Completion Screen**
   - "🎉 Segment Complete!"
   - Score: "4/5 (80%)"
   - Overall accuracy across all videos
   - "Continue Video" button → close overlay, resume video
   - "Review Answers" button → navigate back through questions

5. **Review Mode** (if user already answered)
   - Show all questions with user's previous answers
   - Show correct/incorrect status
   - "Retake Quiz" button to start over
   - "Close" button

**Styling:**
- Modern, clean design
- Match YouTube's dark/light theme (optional)
- Responsive (works on different screen sizes)
- Smooth animations (fade in/out, transitions)

---

### 3.6 Floating Quiz Button
**File:** `extension/content.js` (part of content script)

**Behavior:**
- Appears at segment end time minus 3 seconds
- Disappears at segment end time plus 3 seconds
- Position: Fixed, bottom-right corner of video player
- Badge shows number of unanswered questions
- Smooth fade-in and fade-out animations
- Click → Show quiz overlay
- If user already answered → badge shows checkmark ✓

**Implementation:**
- Monitor `video.currentTime` in `timeupdate` event
- Calculate show/hide based on segment times
- CSS transitions for smooth animations
- Z-index should be high enough to appear over video controls

---

## 📋 Phase 4: Testing & Polish

### 4.1 Manual Testing Checklist
- [ ] Register new user
- [ ] Login with existing user
- [ ] Upload video URL (YouTube)
- [ ] Check video already in cache
- [ ] Monitor WebSocket events during processing
- [ ] Verify segments appear in real-time
- [ ] Answer quiz questions
- [ ] Check answer is saved correctly
- [ ] Retake quiz
- [ ] View user statistics
- [ ] Test browser extension on YouTube
- [ ] Test floating button appears/disappears
- [ ] Test quiz overlay shows correctly
- [ ] Test side panel updates in real-time
- [ ] Test language switching (en/ru/kk)
- [ ] Test with multiple videos in different tabs
- [ ] Test Firefox compatibility

### 4.2 Edge Cases to Handle
- User closes browser during processing → processing continues on server
- User disconnects WebSocket → can reconnect and get current status
- User answers same quiz twice → prevent or allow retake
- Video processing fails → show error in extension
- Backend is down → show offline message
- Invalid video URL → show error
- YouTube changes their DOM → video detection fails (need fallback)
- User has no internet → queue actions for later

### 4.3 Error Handling
- Network errors → retry with exponential backoff
- JWT token expired → refresh automatically
- WebSocket disconnect → reconnect automatically
- Video not found → show friendly error message
- Processing timeout → notify user

### 4.4 Performance Optimization
- Lazy load segments (only load when user opens side panel)
- Cache API responses in extension
- Debounce video time checks
- Minimize DOM manipulations in content script
- Use Shadow DOM to isolate styles

---

## 📋 Phase 5: Deployment & Documentation

### 5.1 Extension Packaging
- Create icons (16x16, 48x48, 128x128)
- Write extension description
- Set correct permissions
- Test on clean browser profile
- Create `.zip` for Chrome Web Store
- Create `.xpi` for Firefox Add-ons

### 5.2 Backend Deployment
- Set `SECRET_KEY` to secure random value
- Configure CORS for production domain
- Set up SSL/HTTPS
- Configure Redis for production
- Set up database backups
- Deploy to cloud (AWS, DigitalOcean, etc.)

### 5.3 Documentation
- Update README.md with:
  - Extension installation instructions
  - API documentation (if public)
  - Deployment guide
  - Configuration options
- Create USER_GUIDE.md for extension usage
- Document API endpoints in OpenAPI/Swagger
- Add screenshots/GIFs of extension in action

---

## 📋 Phase 6: Future Enhancements

### 6.1 Features to Add Later
- Explanations for quiz answers (generated by LLM)
- Leaderboards (compare scores with other users)
- Daily challenges or streaks
- Study mode (review past quizzes)
- Export quiz data (CSV, PDF)
- Share quiz results on social media
- Custom quiz difficulty levels
- Support for more video platforms (Vimeo, Coursera, Udemy)
- Offline mode (save videos and quizzes locally)
- Mobile app (React Native or Flutter)

### 6.2 Optimizations
- Migrate to Celery for background tasks
- Implement Redis caching layer
- Add CDN for serving extension assets
- Use smaller AI models for faster processing
- Batch quiz generation to reduce LLM calls
- Implement rate limiting and abuse prevention

### 6.3 Analytics
- Track user engagement metrics
- Monitor video processing times
- Track quiz completion rates
- A/B test different UI designs
- Error tracking (Sentry or similar)

---

## 🎯 Current Status Summary

**What's Done:**
- ✅ Database architecture (Video, Segment, Quiz, UserAnswer)
- ✅ Authentication (JWT, registration, login)
- ✅ Video endpoints (upload, check, status, segments)
- ✅ Auth endpoints fully functional

**What's Next (Priority Order):**
1. Quiz endpoints (answer submission, review, retake)
2. User stats endpoints (profile, history, topics)
3. WebSocket endpoint for real-time updates
4. Update pipeline to use new Video model
5. Background task processing
6. Browser extension (Chrome + Firefox)
7. Testing and deployment

**Estimated Time:**
- Quiz + User endpoints: 4-6 hours
- WebSocket + Pipeline: 8-12 hours
- Browser extension: 12-16 hours
- Testing + polish: 4-6 hours
- **Total: ~30-40 hours**

---

## 📝 Notes

- All old endpoints (`upload.py`, `video.py`, `general.py`) are commented out and need to be deleted or fully migrated
- Old pipeline code in `pipeline.py`, `db_updater.py`, `task_service.py` references old `Task` model
- Language detection should use `chrome.i18n.getUILanguage()` but allow manual override
- Extension should work offline (graceful degradation)
- Consider rate limiting for API to prevent abuse
- Keep tokens secure in extension (never expose in content script)
- Test with different video lengths (short vs. long)
- Handle videos with no audio (skip transcription)
- Handle videos with no visual content (skip frame analysis)

---

**Last Updated:** 2024-01-23
**Status:** Authentication and basic video endpoints completed, pipeline and extension pending
# Intelligent Project Planning System - Frontend

This is the frontend component of the Intelligent Project Planning System, providing an intuitive user interface for interacting with collaborative AI agents that help transform project requirements into comprehensive plans.

## Architecture

The frontend is built with:

- **Next.js**: React framework with App Router and server components
- **React**: UI library for building interactive interfaces
- **Tailwind CSS**: Utility-first CSS framework for styling
- **Chart.js**: Library for data visualization
- **Socket.io-client**: Real-time communication with the backend
- **React Query**: Data fetching and state management

## Features

- **Interactive Dashboard**: Visual representation of project insights
- **Agent Conversations**: Real-time view of agent discussions
- **Document Upload**: Upload project documents for analysis
- **Project Management**: Create, view, and manage projects
- **Human-in-the-Loop**: Interact with AI agents during the planning process

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running (see backend README)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/project-power-up.git
   cd project-power-up/frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   # or
   yarn install
   ```

3. Create a `.env.local` file with the following variables:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. Run the development server:
   ```bash
   npm run dev
   # or
   yarn dev
   ```

5. Open [http://localhost:3000](http://localhost:3000) in your browser

## Project Structure

```
frontend/
├── app/                    # Next.js App Router
│   ├── api/                # API route handlers
│   ├── dashboard/          # Dashboard pages
│   ├── projects/           # Project management pages
│   ├── layout.tsx          # Root layout component
│   └── page.tsx            # Home page
├── components/             # Reusable React components
│   ├── agents/             # Agent-related components
│   ├── dashboard/          # Dashboard components
│   ├── projects/           # Project components
│   ├── ui/                 # UI components (buttons, cards, etc.)
│   └── layout/             # Layout components
├── lib/                    # Utility functions and hooks
│   ├── api.ts              # API client
│   ├── socket.ts           # WebSocket client
│   └── utils.ts            # Utility functions
├── public/                 # Static assets
├── styles/                 # Global styles
├── types/                  # TypeScript type definitions
├── next.config.js          # Next.js configuration
├── tailwind.config.js      # Tailwind CSS configuration
└── package.json            # Project dependencies
```

## Key Components

### Dashboard

The dashboard provides a visual overview of project insights, including:

- **Technical Analysis**: Architecture recommendations and technology stack
- **Risk Assessment**: Identified risks and mitigation strategies
- **Project Plan**: Timeline, milestones, and resource requirements

### Agent Conversation Interface

The agent conversation interface allows users to:

- View real-time conversations between AI agents
- Provide input and guidance to agents
- Ask clarifying questions
- Review agent reasoning and decision-making

### Project Management

The project management interface enables users to:

- Create new projects
- Upload project documents
- Track project status
- View and export project insights

## Development

### Adding New Pages

To add a new page:

1. Create a new directory or file in the `app` directory
2. Implement the page component
3. Update navigation components if needed

### Creating New Components

To create a new component:

1. Create a new file in the appropriate directory under `components`
2. Implement the component using React and Tailwind CSS
3. Import and use the component in your pages

### API Integration

To integrate with a new API endpoint:

1. Add the endpoint URL and request function in `lib/api.ts`
2. Use React Query hooks to fetch and manage data
3. Handle loading, error, and success states in your components

## Building for Production

To build the frontend for production:

```bash
npm run build
# or
yarn build
```

To start the production server:

```bash
npm start
# or
yarn start
```

## Testing

To run tests:

```bash
npm test
# or
yarn test
```

## License


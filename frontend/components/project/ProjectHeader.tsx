import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeftIcon, PencilIcon, TrashIcon, PlayIcon } from '@heroicons/react/24/outline';

interface ProjectHeaderProps {
  project: {
    id: string;
    name: string;
    description: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
}

export default function ProjectHeader({ project }: ProjectHeaderProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);

  // Status badge component
  const StatusBadge = ({ status }: { status: string }) => {
    let bgColor = 'bg-gray-100 text-gray-800';
    
    if (status === 'completed') {
      bgColor = 'bg-green-100 text-green-800';
    } else if (status === 'analyzing') {
      bgColor = 'bg-blue-100 text-blue-800 animate-pulse-slow';
    } else if (status === 'draft') {
      bgColor = 'bg-gray-100 text-gray-800';
    }
    
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bgColor}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  const handleSave = async () => {
    // In a real implementation, this would call the API to update the project
    // For now, just toggle editing mode
    setIsEditing(false);
    
    // Mock API call
    console.log('Saving project:', { id: project.id, name, description });
  };

  const handleCancel = () => {
    // Reset form values and exit editing mode
    setName(project.name);
    setDescription(project.description);
    setIsEditing(false);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <div className="bg-white shadow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-center mb-4">
          <Link href="/projects" className="text-gray-500 hover:text-gray-700 mr-4">
            <ArrowLeftIcon className="w-5 h-5" />
          </Link>
          <div className="flex-1">
            {isEditing ? (
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="input w-full text-2xl font-bold"
                placeholder="Project Name"
              />
            ) : (
              <div className="flex items-center">
                <h1 className="text-2xl font-bold text-gray-900 mr-3">{project.name}</h1>
                <StatusBadge status={project.status} />
              </div>
            )}
          </div>
          <div className="flex space-x-2">
            {isEditing ? (
              <>
                <button 
                  onClick={handleCancel}
                  className="btn btn-outline"
                >
                  Cancel
                </button>
                <button 
                  onClick={handleSave}
                  className="btn btn-primary"
                >
                  Save
                </button>
              </>
            ) : (
              <>
                <button 
                  onClick={() => setIsEditing(true)}
                  className="btn btn-secondary"
                >
                  <PencilIcon className="w-4 h-4 mr-1" />
                  Edit
                </button>
              </>
            )}
          </div>
        </div>
        
        {isEditing ? (
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input w-full h-24"
            placeholder="Project Description"
          />
        ) : (
          <p className="text-gray-600 mb-4">{project.description}</p>
        )}
        
        <div className="flex items-center text-sm text-gray-500">
          <span className="mr-4">Created: {formatDate(project.created_at)}</span>
          <span>Last updated: {formatDate(project.updated_at)}</span>
        </div>
      </div>
    </div>
  );
}

import React, { useState } from 'react';
import axios from 'axios';
import { Upload, FileText, BarChart3, Download, Target, Eye } from 'lucide-react';

function App() {
  const [resumes, setResumes] = useState([]);
  const [jobDescription, setJobDescription] = useState('');
  const [requiredExperience, setRequiredExperience] = useState(0);
  const [results, setResults] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [visibleContent, setVisibleContent] = useState({});
  const [analyzeClicked, setAnalyzeClicked] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFileChange = (e) => {
    setResumes(Array.from(e.target.files));
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles = droppedFiles.filter(
      (file) =>
        file.type === "application/pdf" ||
        file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    );
    setResumes((prev) => [...prev, ...validFiles]);
  };

  const handleAnalyze = async () => {
    setAnalyzeClicked(true);
    if (resumes.length === 0 || !jobDescription.trim()) {
      if (resumes.length === 0) {
        setError('Please upload at least one resume file.');
      } else if (!jobDescription.trim()) {
        setError('Please provide a job description.');
      }
      return;
    }
    setError(null);
    setAnalyzing(true);

    try {
      const formData = new FormData();
      resumes.forEach((file) => {
        formData.append('resumes', file);
      });
      formData.append('job_description', jobDescription);
      formData.append('required_experience', requiredExperience);

      const response = await axios.post('/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const results = response.data;
      setResults(results);
      const initialVisibility = {};
      results.forEach((_, index) => {
        initialVisibility[`pain-points-${index}`] = false;
        initialVisibility[`summary-${index}`] = false;
      });
      setVisibleContent(initialVisibility);
    } catch (err) {
      setError('An error occurred during analysis. Please try again.');
      console.error('Analysis error:', err);
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleContent = (id) => {
    setVisibleContent((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const getStatusColor = (status) => {
    switch (status.toLowerCase()) {
      case 'shortlisted':
        return 'bg-green-100 text-green-800';
      case 'under consideration':
        return 'bg-yellow-100 text-yellow-800';
      case 'rejected':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600 bg-green-50';
    if (score >= 60) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-white to-blue-50 p-4">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
              <Target className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-blue-600">ATS Resume Analysis System</h1>
          </div>
          <p className="text-lg text-gray-600 font-medium">
            Streamline Your Recruitment Process with AI-Powered Resume Analysis
          </p>
        </div>

        {/* Main Content */}
        <div className="grid lg:grid-cols-2 gap-8">
          {/* File Upload Section */}
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-lg border border-blue-100 overflow-hidden">
              <div className="bg-gradient-to-r from-blue-50 to-blue-100 px-6 py-4 border-b border-blue-200">
                <div className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-blue-600" />
                  <h2 className="text-xl font-bold text-blue-600">Upload Resumes</h2>
                </div>
              </div>
              <div className="p-6">
                <div
                  className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 relative ${
                    isDragOver 
                      ? "border-blue-400 bg-blue-50" 
                      : "border-blue-300 bg-gradient-to-br from-blue-50 to-blue-100 hover:from-blue-100 hover:to-blue-200 hover:border-blue-400 hover:shadow-lg hover:-translate-y-1"
                  }`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.docx"
                    onChange={handleFileChange}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <Upload className="w-8 h-8 mx-auto mb-4 text-blue-600" />
                  <p className="text-lg font-semibold text-blue-600 mb-2">
                    Click to upload or drag and drop files here
                  </p>
                  <p className="text-sm text-gray-600">
                    Upload multiple PDF or DOCX resume files
                  </p>
                </div>

                {resumes.length > 0 && (
                  <div className="mt-4 bg-green-50 border border-green-200 rounded-xl p-4">
                    <p className="text-green-800 font-semibold mb-2 flex items-center gap-2">
                      <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                        <span className="text-white text-xs">✓</span>
                      </div>
                      {resumes.length} file(s) uploaded successfully!
                    </p>
                    <div className="space-y-2">
                      {resumes.map((file, index) => (
                        <div key={index} className="flex items-center gap-2 text-sm text-gray-700">
                          <FileText className="w-4 h-4 text-blue-600" />
                          <span className="font-medium">{index + 1}.</span>
                          <span>{file.name}</span>
                          <span className="text-gray-500">({(file.size / 1024).toFixed(0)} KB)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Job Requirements Section */}
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-lg border border-blue-100 overflow-hidden">
              <div className="bg-gradient-to-r from-orange-50 to-orange-100 px-6 py-4 border-b border-orange-200">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 bg-orange-500 rounded flex items-center justify-center">
                    <FileText className="w-3 h-3 text-white" />
                  </div>
                  <h2 className="text-xl font-bold text-orange-600">Job Requirements</h2>
                </div>
              </div>
              <div className="p-6 space-y-6">
                <div>
                  <label className="block text-gray-700 font-semibold mb-2">
                    Required Experience (years)
                  </label>
                  <select
                    value={requiredExperience}
                    onChange={(e) => setRequiredExperience(e.target.value)}
                    className="w-24 bg-white border-2 border-blue-200 rounded-lg p-3 text-gray-700 focus:border-blue-400 focus:ring-2 focus:ring-blue-200 focus:outline-none"
                  >
                    {Array.from({ length: 21 }, (_, i) => (
                      <option key={i} value={i}>{i}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">
                    Job Description
                  </label>
                  <textarea
                    value={jobDescription}
                    onChange={(e) => setJobDescription(e.target.value)}
                    placeholder="Enter detailed job description including:
• Required skills and technologies
• Key responsibilities  
• Educational qualifications
• Preferred certifications
• Company culture fit criteria..."
                    className="w-full h-48 bg-white border-2 border-blue-200 rounded-lg p-3 text-gray-700 focus:border-blue-400 focus:ring-2 focus:ring-blue-200 focus:outline-none resize-none"
                  />
                </div>

                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className={`w-full bg-gradient-to-r from-blue-600 to-blue-700 text-white font-bold py-3 px-6 rounded-lg shadow-lg hover:from-blue-700 hover:to-blue-800 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 flex items-center justify-center gap-2 ${
                    analyzing ? 'opacity-70 cursor-not-allowed' : ''
                  }`}
                >
                  {analyzing ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <BarChart3 className="w-4 h-4" />
                      ANALYZE RESUMES
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            <div className="flex items-center gap-2">
              <span className="text-red-500">❌</span>
              {error}
            </div>
          </div>
        )}

        {/* Results Section */}
        <div className="space-y-6">
          {/* Analysis Results Header */}
          <div className="bg-gradient-to-r from-blue-50 to-blue-100 border-2 border-blue-200 rounded-xl p-6">
            <div className="text-center">
              <div className="flex items-center justify-center gap-2 mb-2">
                <BarChart3 className="w-6 h-6 text-blue-600" />
                <h2 className="text-2xl font-bold text-blue-700">Analysis Results</h2>
              </div>
              <p className="text-blue-600">Comprehensive resume analysis and candidate ranking</p>
            </div>
          </div>

          {/* Results Table */}
          {results.length > 0 ? (
            <div className="bg-white rounded-xl shadow-lg border border-blue-100 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-blue-50 border-b border-blue-200">
                      <th className="px-6 py-4 text-left text-sm font-bold text-blue-700">Name</th>
                      <th className="px-6 py-4 text-left text-sm font-bold text-blue-700">HR Score</th>
                      <th className="px-6 py-4 text-left text-sm font-bold text-blue-700">HR Issues</th>
                      <th className="px-6 py-4 text-left text-sm font-bold text-blue-700">Summary</th>
                      <th className="px-6 py-4 text-left text-sm font-bold text-blue-700">Status</th>
                      <th className="px-6 py-4 text-left text-sm font-bold text-blue-700">Resume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((result, index) => (
                      <tr key={index} className="border-b border-blue-100 hover:bg-blue-50 transition-colors">
                        <td className="px-6 py-4 font-medium text-gray-900">{result.candidate_name}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(result.score)}`}>
                            {result.score}%
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <button
                            className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg px-3 py-1 text-sm hover:from-blue-700 hover:to-blue-800 transition-all duration-300 flex items-center gap-1"
                            onClick={() => toggleContent(`pain-points-${index}`)}
                          >
                            <Eye className="w-3 h-3" />
                            View
                          </button>
                          {visibleContent[`pain-points-${index}`] && (
                            <div className="mt-2 bg-gray-50 rounded-lg p-3">
                              <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
                                {result.pain_points.map((point, i) => (
                                  <li key={i}>{point}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <button
                            className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg px-3 py-1 text-sm hover:from-blue-700 hover:to-blue-800 transition-all duration-300 flex items-center gap-1"
                            onClick={() => toggleContent(`summary-${index}`)}
                          >
                            <Eye className="w-3 h-3" />
                            View
                          </button>
                          {visibleContent[`summary-${index}`] && (
                            <div className="mt-2 bg-gray-50 rounded-lg p-3 text-sm text-gray-700">
                              {result.summary}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(result.status)}`}>
                            {result.status}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <a
                            href={`/uploads/${encodeURIComponent(result.resume_name)}`}
                            download
                            className="text-blue-600 font-semibold hover:text-blue-800 hover:underline flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" />
                            Download
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="bg-white border-2 border-dashed border-blue-300 rounded-xl p-12">
              <div className="text-center">
                <div className="flex items-center justify-center gap-2 mb-4">
                  <FileText className="w-8 h-8 text-gray-400" />
                  <h3 className="text-xl font-semibold text-gray-700">Detailed Results Table</h3>
                </div>
                <p className="text-gray-600">
                  {analyzeClicked
                    ? "No results to display. Please ensure valid resumes and job description are provided."
                    : 'Upload resumes and click "Analyze" to see comprehensive candidate scoring and ranking'}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
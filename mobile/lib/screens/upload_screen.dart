import 'dart:io' show File;

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';

import '../core/network/app_error.dart';
import '../core/theme/app_theme.dart';
import '../services/api_service.dart';
import 'document_detail_screen.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final ApiService _apiService = ApiService();

  PlatformFile? _selectedFile;
  String _documentType = 'INSURANCE_POLICY';
  bool _isUploading = false;
  String _currentStep = '';

  Future<void> _pickFile() async {
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'png', 'jpg', 'jpeg'],
    );

    if (result != null && result.files.isNotEmpty) {
      final file = result.files.first;

      // Validate 25 MB max size
      if (file.size > 25 * 1024 * 1024) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('File exceeds 25 MB limit.')),
        );
        return;
      }

      setState(() {
        _selectedFile = file;
      });
    }
  }

  Future<void> _startUploadAndProcess() async {
    if (_selectedFile == null) return;

    setState(() {
      _isUploading = true;
      _currentStep = 'Initializing secure upload vault...';
    });

    try {
      final initData = await _apiService.initUpload(
        fileName: _selectedFile!.name,
        fileSizeBytes: _selectedFile!.size,
        mimeType: _selectedFile!.extension == 'pdf'
            ? 'application/pdf'
            : (_selectedFile!.extension == 'png'
                  ? 'image/png'
                  : (_selectedFile!.extension == 'webp'
                        ? 'image/webp'
                        : 'image/jpeg')),
        documentType: _documentType,
      );

      final documentId = initData['documentId'] as String;
      final uploadUrl = initData['uploadUrl'] as String;

      // ISSUE-002: actually PUT the bytes to the presigned vault URL, then
      // let the server verify them before processing is allowed.
      setState(() {
        _currentStep = 'Uploading encrypted copy to your private vault...';
      });

      // file_picker returns in-memory bytes on web; on mobile platforms we
      // must read from the picked path.
      final bytes =
          _selectedFile!.bytes ??
          (_selectedFile!.path != null
              ? await File(_selectedFile!.path!).readAsBytes()
              : null);
      if (bytes == null) {
        throw Exception(
          'Could not read the selected file. Please pick it again.',
        );
      }
      final mimeType = _selectedFile!.extension == 'pdf'
          ? 'application/pdf'
          : (_selectedFile!.extension == 'png'
                ? 'image/png'
                : (_selectedFile!.extension == 'webp'
                      ? 'image/webp'
                      : 'image/jpeg'));

      await _apiService.putPresigned(
        uploadUrl: uploadUrl,
        bytes: bytes,
        mimeType: mimeType,
      );

      setState(() {
        _currentStep = 'Verifying upload integrity...';
      });

      final checksum = sha256.convert(bytes).toString();
      await _apiService.completeUpload(documentId, checksumSha256: checksum);

      setState(() {
        _currentStep = 'Extracting structured facts and verifying citations...';
      });

      await _apiService.processDocument(documentId);

      if (!mounted) return;

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => DocumentDetailScreen(documentId: documentId),
        ),
      );
    } catch (e) {
      setState(() {
        _isUploading = false;
      });
      if (!mounted) return;
      // BE-4: structured error → friendly copy only.
      final err = AppError.from(e);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(err.userMessage),
          backgroundColor: AppColors.riskHigh,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Upload Document')),
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (!_isUploading) ...[
              const Text(
                'Select Document Type',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              DropdownButtonFormField<String>(
                initialValue: _documentType,
                decoration: const InputDecoration(),
                items: const [
                  DropdownMenuItem(
                    value: 'INSURANCE_POLICY',
                    child: Text('Insurance Policy'),
                  ),
                  DropdownMenuItem(
                    value: 'GST_INVOICE',
                    child: Text('GST Invoice / Tax Bill'),
                  ),
                  DropdownMenuItem(
                    value: 'BILL_RECEIPT',
                    child: Text('Utility Bill / Receipt'),
                  ),
                  DropdownMenuItem(
                    value: 'CONTRACT',
                    child: Text('Rental / Service Contract'),
                  ),
                  DropdownMenuItem(
                    value: 'OTHER',
                    child: Text('Other Document'),
                  ),
                ],
                onChanged: (val) {
                  if (val != null) setState(() => _documentType = val);
                },
              ),
              const SizedBox(height: AppSpacing.xl),
              GestureDetector(
                onTap: _pickFile,
                child: Container(
                  height: 180,
                  decoration: BoxDecoration(
                    color: AppColors.elevated,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: _selectedFile != null
                          ? AppColors.primary
                          : const Color(0xFFD1D5DB),
                      width: 2,
                    ),
                  ),
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          _selectedFile != null
                              ? Icons.check_circle
                              : Icons.cloud_upload_outlined,
                          size: 48,
                          color: _selectedFile != null
                              ? AppColors.success
                              : AppColors.primary,
                        ),
                        const SizedBox(height: AppSpacing.sm),
                        Text(
                          _selectedFile != null
                              ? _selectedFile!.name
                              : 'Tap to select PDF or image',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            color: _selectedFile != null
                                ? AppColors.textPrimary
                                : AppColors.primary,
                          ),
                        ),
                        if (_selectedFile != null)
                          Text(
                            '${(_selectedFile!.size / 1024).toStringAsFixed(1)} KB',
                            style: const TextStyle(
                              fontSize: 12,
                              color: AppColors.textSecondary,
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
              const Spacer(),
              ElevatedButton(
                onPressed: _selectedFile != null
                    ? _startUploadAndProcess
                    : null,
                child: const Text('Process & Extract'),
              ),
            ] else ...[
              const Spacer(),
              const Center(
                child: SizedBox(
                  width: 56,
                  height: 56,
                  child: CircularProgressIndicator(strokeWidth: 3),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              Text(
                _currentStep,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              const Text(
                'This document is being analyzed with grounded evidence verification.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
              const Spacer(),
            ],
          ],
        ),
      ),
    );
  }
}
